import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../theme/cyberforge_theme.dart';

final class InfrastructureMapPage extends StatefulWidget {
  const InfrastructureMapPage({super.key});

  @override
  State<InfrastructureMapPage> createState() => _InfrastructureMapPageState();
}

final class _InfrastructureMapPageState extends State<InfrastructureMapPage> {
  static const _baseUri = String.fromEnvironment(
    'CYBERFORGE_SIDECAR_URL',
    defaultValue: 'http://127.0.0.1:8788',
  );

  final _nodes = <_InfraNode>[
    _InfraNode(
      id: 'internet',
      label: 'Internet',
      kind: 'internet',
      zone: 'external',
      position: const Offset(90, 170),
      internetFacing: true,
      controls: const {'logging': true, 'segmented': true},
    ),
    _InfraNode(
      id: 'edge-router',
      label: 'Edge router',
      kind: 'router',
      zone: 'edge',
      position: const Offset(290, 170),
      criticality: .9,
      internetFacing: true,
      controls: const {'logging': true, 'segmented': true, 'managed': true},
    ),
    _InfraNode(
      id: 'home-device',
      label: 'Primary device',
      kind: 'device',
      zone: 'trusted-lan',
      position: const Offset(500, 90),
      controls: const {'encryption': true, 'logging': true, 'managed': true},
    ),
    _InfraNode(
      id: 'cloud-admin',
      label: 'Cloud admin IAM',
      kind: 'iam',
      zone: 'cloud',
      position: const Offset(500, 260),
      criticality: .95,
      privileged: true,
      controls: const {'mfa': true, 'logging': true, 'managed': true},
    ),
  ];

  final _edges = <_InfraEdge>[
    const _InfraEdge(source: 'internet', target: 'edge-router', kind: 'routes'),
    const _InfraEdge(source: 'edge-router', target: 'home-device', kind: 'connects'),
    const _InfraEdge(source: 'home-device', target: 'cloud-admin', kind: 'authenticates'),
  ];

  String? _selectedNodeId;
  String? _linkSourceId;
  String? _machineId;
  String? _machineSalt;
  Map<String, dynamic>? _review;
  bool _busy = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Infrastructure Workflow Map'),
        actions: [
          IconButton(
            tooltip: 'Generate privacy-preserving machine ID',
            onPressed: _busy ? null : _generateMachineId,
            icon: const Icon(Icons.fingerprint),
          ),
          IconButton(
            tooltip: 'Review entire infrastructure map',
            onPressed: _busy ? null : _reviewMap,
            icon: const Icon(Icons.psychology_alt),
          ),
        ],
      ),
      body: Column(
        children: [
          _toolbar(),
          if (_error != null)
            MaterialBanner(
              content: Text(_error!),
              actions: [
                TextButton(
                  onPressed: () => setState(() => _error = null),
                  child: const Text('DISMISS'),
                ),
              ],
            ),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 1050;
                final canvas = _mapCanvas();
                final inspector = _inspector();
                return wide
                    ? Row(
                        children: [
                          Expanded(flex: 3, child: canvas),
                          const VerticalDivider(width: 1),
                          SizedBox(width: 390, child: inspector),
                        ],
                      )
                    : Column(
                        children: [
                          Expanded(flex: 3, child: canvas),
                          const Divider(height: 1),
                          Expanded(flex: 2, child: inspector),
                        ],
                      );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _toolbar() => Container(
    padding: const EdgeInsets.all(12),
    decoration: const BoxDecoration(
      color: CyberForgeColors.surface,
      border: Border(bottom: BorderSide(color: CyberForgeColors.grid)),
    ),
    child: Wrap(
      spacing: 10,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        FilledButton.icon(
          onPressed: _busy ? null : _addNode,
          icon: const Icon(Icons.add_box_outlined),
          label: const Text('ADD COMPONENT'),
        ),
        OutlinedButton.icon(
          onPressed: _selectedNodeId == null ? null : _beginLink,
          icon: const Icon(Icons.account_tree_outlined),
          label: Text(_linkSourceId == null ? 'START LINK' : 'CANCEL LINK'),
        ),
        OutlinedButton.icon(
          onPressed: _selectedNodeId == null ? null : _removeSelected,
          icon: const Icon(Icons.delete_outline),
          label: const Text('REMOVE'),
        ),
        OutlinedButton.icon(
          onPressed: _busy ? null : _generateMachineId,
          icon: const Icon(Icons.fingerprint),
          label: const Text('MACHINE ID'),
        ),
        FilledButton.icon(
          onPressed: _busy ? null : _reviewMap,
          icon: _busy
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.travel_explore),
          label: Text(_busy ? 'REVIEWING' : 'REVIEW WHOLE MAP'),
        ),
        Text(
          '${_nodes.length} nodes · ${_edges.length} links',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    ),
  );

  Widget _mapCanvas() => Container(
    color: CyberForgeColors.background,
    child: InteractiveViewer(
      minScale: .5,
      maxScale: 2.5,
      constrained: false,
      boundaryMargin: const EdgeInsets.all(500),
      child: SizedBox(
        width: 900,
        height: 620,
        child: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: _InfrastructurePainter(nodes: _nodes, edges: _edges),
              ),
            ),
            for (final node in _nodes)
              Positioned(
                left: node.position.dx,
                top: node.position.dy,
                child: GestureDetector(
                  onTap: () => _selectNode(node.id),
                  onPanUpdate: (details) {
                    setState(() {
                      node.position += details.delta;
                    });
                  },
                  child: _nodeCard(node),
                ),
              ),
          ],
        ),
      ),
    ),
  );

  Widget _nodeCard(_InfraNode node) {
    final selected = node.id == _selectedNodeId;
    final linking = node.id == _linkSourceId;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 140),
      width: 150,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: selected ? CyberForgeColors.surfaceRaised : CyberForgeColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: linking
              ? CyberForgeColors.amber
              : selected
              ? CyberForgeColors.cyan
              : CyberForgeColors.grid,
          width: selected || linking ? 2 : 1,
        ),
        boxShadow: const [BoxShadow(blurRadius: 18, color: Color(0x55000000))],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_iconFor(node.kind), color: _colorFor(node.kind), size: 30),
          const SizedBox(height: 7),
          Text(
            node.label,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            '${node.kind} · ${node.zone}',
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _inspector() {
    final selected = _nodes.where((node) => node.id == _selectedNodeId).firstOrNull;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('MAP INSPECTOR', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          'Model devices, routers, VPNs, VPCs, IAM identities, cloud accounts, servers, databases, APIs, SaaS dependencies, and home-lab equipment.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        if (_machineId != null)
          _panel(
            'MACHINE ID',
            SelectableText('$_machineId\nSalt: ${_machineSalt ?? ''}'),
          ),
        if (selected != null) ...[
          _panel(
            'SELECTED COMPONENT',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(selected.label, style: Theme.of(context).textTheme.titleMedium),
                Text('${selected.kind} · ${selected.zone}'),
                const SizedBox(height: 10),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Internet facing'),
                  value: selected.internetFacing,
                  onChanged: (value) => setState(() => selected.internetFacing = value),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Privileged'),
                  value: selected.privileged,
                  onChanged: (value) => setState(() => selected.privileged = value),
                ),
                for (final control in const [
                  'mfa',
                  'encryption',
                  'logging',
                  'backup',
                  'segmented',
                  'managed',
                ])
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    title: Text(control.toUpperCase()),
                    value: selected.controls[control] ?? false,
                    onChanged: (value) => setState(
                      () => selected.controls[control] = value ?? false,
                    ),
                  ),
              ],
            ),
          ),
        ],
        if (_review != null) _reviewPanel(_review!),
      ],
    );
  }

  Widget _reviewPanel(Map<String, dynamic> response) {
    final topology = _map(response['topology']);
    final findings = (topology['findings'] as List<dynamic>? ?? const [])
        .whereType<Map>()
        .map((item) => item.map((key, value) => MapEntry(key.toString(), value)))
        .toList();
    return _panel(
      'WHOLE-ESTATE REVIEW',
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Topology pressure: ${(_number(topology['topologyPressure']) * 100).toStringAsFixed(1)}%',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            'Control coverage: ${(_number(topology['controlCoverage']) * 100).toStringAsFixed(1)}%',
          ),
          Text('Graph digest: ${topology['graphDigest'] ?? ''}'),
          const SizedBox(height: 12),
          for (final finding in findings.take(12))
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${finding['severity']?.toString().toUpperCase()} · ${finding['title']}',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 5),
                    Text(finding['explanation']?.toString() ?? ''),
                    const SizedBox(height: 5),
                    Text('Control: ${finding['control'] ?? ''}'),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _panel(String title, Widget child) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          child,
        ],
      ),
    ),
  );

  Future<void> _addNode() async {
    final label = TextEditingController();
    final zone = TextEditingController(text: 'trusted-lan');
    var kind = 'device';
    final created = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add infrastructure component'),
        content: StatefulBuilder(
          builder: (context, setDialogState) => SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(controller: label, decoration: const InputDecoration(labelText: 'Label')),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: kind,
                  decoration: const InputDecoration(labelText: 'Component type'),
                  items: _kinds
                      .map((value) => DropdownMenuItem(value: value, child: Text(value)))
                      .toList(),
                  onChanged: (value) => setDialogState(() => kind = value ?? kind),
                ),
                const SizedBox(height: 12),
                TextField(controller: zone, decoration: const InputDecoration(labelText: 'Zone / VPC / site')),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('CANCEL')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('ADD')),
        ],
      ),
    );
    if (created != true) return;
    final id = '${kind.replaceAll('-', '_')}_${DateTime.now().microsecondsSinceEpoch}';
    setState(() {
      _nodes.add(
        _InfraNode(
          id: id,
          label: label.text.trim().isEmpty ? kind : label.text.trim(),
          kind: kind,
          zone: zone.text.trim().isEmpty ? 'unassigned' : zone.text.trim(),
          position: Offset(120 + math.Random().nextInt(520).toDouble(), 80 + math.Random().nextInt(360).toDouble()),
        ),
      );
      _selectedNodeId = id;
    });
  }

  void _selectNode(String id) {
    if (_linkSourceId != null && _linkSourceId != id) {
      setState(() {
        _edges.add(_InfraEdge(source: _linkSourceId!, target: id, kind: 'connects'));
        _linkSourceId = null;
        _selectedNodeId = id;
      });
      return;
    }
    setState(() => _selectedNodeId = id);
  }

  void _beginLink() {
    setState(() {
      _linkSourceId = _linkSourceId == null ? _selectedNodeId : null;
    });
  }

  void _removeSelected() {
    final id = _selectedNodeId;
    if (id == null) return;
    setState(() {
      _nodes.removeWhere((node) => node.id == id);
      _edges.removeWhere((edge) => edge.source == id || edge.target == id);
      _selectedNodeId = null;
      if (_linkSourceId == id) _linkSourceId = null;
    });
  }

  Future<void> _generateMachineId() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final response = await http.post(
        Uri.parse('$_baseUri/v1/infrastructure/machine-id'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'salt': _machineSalt}),
      );
      final body = _decode(response);
      setState(() {
        _machineId = body['machineId']?.toString();
        _machineSalt = body['salt']?.toString();
      });
    } catch (error) {
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reviewMap() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final packet = {
        'name': 'CyberForge infrastructure workflow map',
        'scale': _nodes.length < 20 ? 'home-or-small' : _nodes.length < 200 ? 'medium' : 'large',
        'machineId': _machineId,
        'includeRemoteModels': false,
        'authorization': {
          'authorized': true,
          'statement': 'I own or am explicitly authorized to model and defensively review every component in this infrastructure map.',
          'scope': 'CyberForge infrastructure workflow map',
          'synthetic': true,
        },
        'nodes': _nodes.map((node) => node.toJson()).toList(),
        'edges': _edges.map((edge) => edge.toJson()).toList(),
      };
      final response = await http.post(
        Uri.parse('$_baseUri/v1/infrastructure/review'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode(packet),
      ).timeout(const Duration(minutes: 8));
      final body = _decode(response);
      setState(() => _review = body);
    } catch (error) {
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded = jsonDecode(response.body);
    final body = decoded is Map
        ? decoded.map((key, value) => MapEntry(key.toString(), value))
        : <String, dynamic>{'value': decoded};
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError(body['detail']?.toString() ?? 'Infrastructure request failed.');
    }
    return body;
  }

  static Map<String, dynamic> _map(dynamic value) => value is Map
      ? value.map((key, item) => MapEntry(key.toString(), item))
      : <String, dynamic>{};

  static double _number(dynamic value) => value is num ? value.toDouble() : 0;

  static IconData _iconFor(String kind) => switch (kind) {
    'router' => Icons.router,
    'switch' => Icons.hub,
    'firewall' => Icons.shield,
    'vpn' => Icons.vpn_lock,
    'vpc' => Icons.cloud_queue,
    'iam' || 'identity-provider' => Icons.badge,
    'cloud-account' => Icons.cloud,
    'server' => Icons.dns,
    'database' => Icons.storage,
    'api' => Icons.api,
    'internet' => Icons.public,
    'iot' => Icons.sensors,
    _ => Icons.devices,
  };

  static Color _colorFor(String kind) => switch (kind) {
    'iam' || 'identity-provider' => CyberForgeColors.violet,
    'router' || 'switch' || 'firewall' || 'vpn' => CyberForgeColors.cyan,
    'cloud-account' || 'vpc' || 'saas' => CyberForgeColors.blue,
    'database' || 'storage' => CyberForgeColors.amber,
    'internet' => CyberForgeColors.red,
    _ => CyberForgeColors.green,
  };

  static const _kinds = [
    'device',
    'router',
    'switch',
    'firewall',
    'vpn',
    'vpc',
    'subnet',
    'iam',
    'cloud-account',
    'server',
    'endpoint',
    'database',
    'api',
    'saas',
    'identity-provider',
    'storage',
    'iot',
    'facility',
    'internet',
  ];
}

final class _InfraNode {
  _InfraNode({
    required this.id,
    required this.label,
    required this.kind,
    required this.zone,
    required this.position,
    this.criticality = .6,
    this.exposure = .4,
    this.internetFacing = false,
    this.privileged = false,
    Map<String, bool> controls = const {},
  }) : controls = {
         'mfa': false,
         'encryption': false,
         'logging': false,
         'backup': false,
         'segmented': false,
         'managed': false,
         ...controls,
       };

  final String id;
  final String label;
  final String kind;
  final String zone;
  Offset position;
  final double criticality;
  final double exposure;
  bool internetFacing;
  bool privileged;
  final Map<String, bool> controls;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'kind': kind,
    'zone': zone,
    'provider': kind.contains('cloud') || kind == 'vpc' || kind == 'iam' ? 'cloud' : 'local',
    'criticality': criticality,
    'exposure': exposure,
    'controlStrength': controls.values.where((value) => value).length / controls.length,
    'telemetryConfidence': controls['logging'] == true ? .82 : .45,
    'internetFacing': internetFacing,
    'privileged': privileged,
    'dataClass': kind == 'database' || kind == 'storage' ? 'confidential' : 'internal',
    'controls': controls,
    'notes': ['authored in CyberForge workflow map'],
  };
}

final class _InfraEdge {
  const _InfraEdge({required this.source, required this.target, required this.kind});

  final String source;
  final String target;
  final String kind;

  Map<String, dynamic> toJson() => {
    'source': source,
    'target': target,
    'kind': kind,
    'trust': .65,
    'controlStrength': .55,
    'bidirectional': true,
  };
}

final class _InfrastructurePainter extends CustomPainter {
  const _InfrastructurePainter({required this.nodes, required this.edges});

  final List<_InfraNode> nodes;
  final List<_InfraEdge> edges;

  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = CyberForgeColors.grid.withValues(alpha: .28)
      ..strokeWidth = 1;
    for (var x = 0.0; x < size.width; x += 28) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (var y = 0.0; y < size.height; y += 28) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }

    final byId = {for (final node in nodes) node.id: node};
    final line = Paint()
      ..color = CyberForgeColors.cyan.withValues(alpha: .65)
      ..strokeWidth = 2.2
      ..style = PaintingStyle.stroke;
    for (final edge in edges) {
      final source = byId[edge.source];
      final target = byId[edge.target];
      if (source == null || target == null) continue;
      final a = source.position + const Offset(75, 45);
      final b = target.position + const Offset(75, 45);
      final control = Offset((a.dx + b.dx) / 2, math.min(a.dy, b.dy) - 35);
      final path = Path()
        ..moveTo(a.dx, a.dy)
        ..quadraticBezierTo(control.dx, control.dy, b.dx, b.dy);
      canvas.drawPath(path, line);
    }
  }

  @override
  bool shouldRepaint(covariant _InfrastructurePainter oldDelegate) => true;
}

extension<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
