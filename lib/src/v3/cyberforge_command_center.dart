import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/cyberforge_theme.dart';
import 'models.dart';
import 'sidecar_client.dart';
import 'widgets/gamma_simstation_display.dart';
import 'widgets/risk_arc.dart';
import 'widgets/surface_matrix.dart';
import 'widgets/timeline_strip.dart';

final class CyberForgeCommandCenter extends StatefulWidget {
  const CyberForgeCommandCenter({super.key});

  @override
  State<CyberForgeCommandCenter> createState() =>
      _CyberForgeCommandCenterState();
}

final class _CyberForgeCommandCenterState
    extends State<CyberForgeCommandCenter> {
  final _client = CyberForgeSidecarClient();
  final _locationController = TextEditingController(text: 'Named region only');
  final _latitudeController = TextEditingController();
  final _longitudeController = TextEditingController();
  final _worldsController = TextEditingController(text: '12000');
  final _simcomController = TextEditingController(text: 'boot');
  final _terminalScroll = ScrollController();
  final _localModelPathController = TextEditingController();

  CyberForgeHealth _health = CyberForgeHealth.offline();
  Map<String, dynamic>? _packet;
  ScanReport? _report;
  var _selectedIndex = 0;
  var _loading = true;
  var _running = false;
  var _includeRemote = false;
  var _includeNewsCapture = false;
  String? _error;
  final List<String> _terminal = <String>[
    'CyberForge SIMCOM v3',
    'Local-first defensive terminal. Type help for commands.',
  ];

  @override
  void initState() {
    super.initState();
    unawaited(_initialize());
  }

  @override
  void dispose() {
    _locationController.dispose();
    _latitudeController.dispose();
    _longitudeController.dispose();
    _worldsController.dispose();
    _simcomController.dispose();
    _terminalScroll.dispose();
    _localModelPathController.dispose();
    super.dispose();
  }

  Future<void> _initialize() async {
    setState(() => _loading = true);
    final health = await _client.health();
    Map<String, dynamic> packet;
    if (health.online) {
      try {
        packet = await _client.defaultScenario();
      } on Object catch (error) {
        packet = _fallbackPacket();
        _error = error.toString();
      }
    } else {
      packet = _fallbackPacket();
    }
    if (!mounted) return;
    setState(() {
      _health = health;
      _packet = packet;
      _loading = false;
      _syncControllers(packet);
    });
  }

  void _syncControllers(Map<String, dynamic> packet) {
    final location = _asMap(packet['location']);
    _locationController.text = location['name']?.toString() ?? '';
    _latitudeController.text = location['latitude']?.toString() ?? '';
    _longitudeController.text = location['longitude']?.toString() ?? '';
    _worldsController.text = packet['worlds']?.toString() ?? '12000';
    _includeRemote = packet['includeRemoteModels'] == true;
    _includeNewsCapture = packet['includeNewsCapture'] == true;
  }

  Future<void> _refreshHealth() async {
    final health = await _client.health();
    if (!mounted) return;
    setState(() => _health = health);
  }

  Future<void> _runScan() async {
    if (!_health.online) {
      setState(() {
        _error =
            'Start the local sidecar with ./tool/run_dev.sh before running the full scan.';
      });
      return;
    }
    final packet = _buildPacket();
    setState(() {
      _running = true;
      _error = null;
      _packet = packet;
    });
    try {
      final report = await _client.scan(packet);
      if (!mounted) return;
      setState(() {
        _report = report;
        _selectedIndex = 0;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Map<String, dynamic> _buildPacket() {
    final packet = Map<String, dynamic>.from(_packet ?? _fallbackPacket());
    packet['worlds'] = int.tryParse(_worldsController.text.trim()) ?? 12000;
    packet['includeRemoteModels'] = _includeRemote;
    packet['includeNewsCapture'] = _includeNewsCapture;
    packet['location'] = <String, dynamic>{
      'name': _locationController.text.trim().isEmpty
          ? 'Unspecified named location'
          : _locationController.text.trim(),
      'latitude': double.tryParse(_latitudeController.text.trim()),
      'longitude': double.tryParse(_longitudeController.text.trim()),
      'coordinatesOptional': true,
    };
    final surfaces = (packet['surfaces'] as List<dynamic>? ?? const <dynamic>[])
        .whereType<Map>()
        .map(
          (Map<dynamic, dynamic> value) => value.map(
            (dynamic key, dynamic item) => MapEntry(key.toString(), item),
          ),
        )
        .toList();
    for (final surface in surfaces) {
      if ((surface['location']?.toString() ?? '').isEmpty ||
          surface['location'] == 'Named region only') {
        surface['location'] = _locationController.text.trim();
      }
    }
    packet['surfaces'] = surfaces;
    packet['authorization'] = <String, dynamic>{
      'authorized': true,
      'statement':
          'I own or am explicitly authorized to simulate every surface in this scenario.',
      'scope':
          packet['name']?.toString() ?? 'CyberForge defensive digital twin',
      'synthetic': true,
    };
    return packet;
  }

  Future<void> _sendSimcom() async {
    final command = _simcomController.text.trim();
    if (command.isEmpty) return;
    setState(() {
      _terminal.add('> $command');
      _simcomController.clear();
    });
    try {
      if (!_health.online) {
        throw const SidecarException(
          'Sidecar offline. Start ./tool/run_dev.sh.',
        );
      }
      final response = await _client.simcom(command, packet: _buildPacket());
      if (!mounted) return;
      setState(() => _terminal.addAll(response.lines));
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _terminal.add('[ERROR] $error'));
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_terminalScroll.hasClients) {
        _terminalScroll.animateTo(
          _terminalScroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final wide = constraints.maxWidth >= 980;
        return Scaffold(
          appBar: wide ? null : _mobileAppBar(),
          body: Row(
            children: <Widget>[
              if (wide) _navigationRail(),
              if (wide) const VerticalDivider(width: 1),
              Expanded(
                child: Column(
                  children: <Widget>[
                    if (wide) _topBar(),
                    if (_error != null) _errorBanner(),
                    Expanded(
                      child: _loading
                          ? const Center(child: CircularProgressIndicator())
                          : IndexedStack(
                              index: _selectedIndex,
                              children: <Widget>[
                                _overviewPage(),
                                _scannerPage(),
                                _simstationPage(),
                                _councilPage(),
                                _vaultPage(),
                                _modelDownloaderPage(),
                                _simcomPage(),
                                _safetyPage(),
                                _settingsPage(),
                              ],
                            ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          bottomNavigationBar: wide
              ? null
              : NavigationBar(
                  selectedIndex: _selectedIndex.clamp(0, 8).toInt(),
                  onDestinationSelected: (int value) {
                    setState(() => _selectedIndex = value);
                  },
                  destinations: const <NavigationDestination>[
                    NavigationDestination(
                      icon: Icon(Icons.radar),
                      label: 'Overview',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.travel_explore),
                      label: 'Scanner',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.memory),
                      label: 'Sim',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.psychology),
                      label: 'Council',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.security),
                      label: 'Vault',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.download_for_offline),
                      label: 'Models',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.terminal),
                      label: 'SIMCOM',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.policy),
                      label: 'Safety',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.settings),
                      label: 'Settings',
                    ),
                  ],
                ),
        );
      },
    );
  }

  PreferredSizeWidget _mobileAppBar() => AppBar(
    title: const _Brand(compact: true),
    actions: <Widget>[
      IconButton(
        tooltip: 'SIMCOM',
        onPressed: () => setState(() => _selectedIndex = 5),
        icon: const Icon(Icons.terminal),
      ),
      IconButton(
        tooltip: 'Safety',
        onPressed: () => setState(() => _selectedIndex = 6),
        icon: const Icon(Icons.policy),
      ),
    ],
  );

  Widget _navigationRail() => NavigationRail(
    extended: true,
    minExtendedWidth: 246,
    selectedIndex: _selectedIndex,
    onDestinationSelected: (int index) =>
        setState(() => _selectedIndex = index),
    leading: const Padding(
      padding: EdgeInsets.fromLTRB(18, 22, 18, 24),
      child: _Brand(),
    ),
    destinations: const <NavigationRailDestination>[
      NavigationRailDestination(
        icon: Icon(Icons.radar),
        label: Text('Command overview'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.travel_explore),
        label: Text('Super scanner'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.memory),
        label: Text('Gamma simstation'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.psychology),
        label: Text('Model council'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.security),
        label: Text('Vault & models'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.download_for_offline),
        label: Text('Model downloader'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.terminal),
        label: Text('SIMCOM terminal'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.policy),
        label: Text('Safety boundary'),
      ),
      NavigationRailDestination(
        icon: Icon(Icons.settings),
        label: Text('Settings'),
      ),
    ],
  );

  Widget _topBar() => Container(
    height: 74,
    padding: const EdgeInsets.symmetric(horizontal: 24),
    decoration: const BoxDecoration(
      color: CyberForgeColors.surface,
      border: Border(bottom: BorderSide(color: CyberForgeColors.grid)),
    ),
    child: Row(
      children: <Widget>[
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Text(
                _pageTitle(_selectedIndex),
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(
                'Authorized blue-team simulation · local-first · no live exploitation',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        _ConnectionPill(health: _health),
        const SizedBox(width: 12),
        IconButton(
          tooltip: 'Refresh sidecar status',
          onPressed: _refreshHealth,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
  );

  Widget _errorBanner() => MaterialBanner(
    backgroundColor: CyberForgeColors.red.withValues(alpha: .10),
    content: Text(_error!),
    actions: <Widget>[
      TextButton(
        onPressed: () => setState(() => _error = null),
        child: const Text('DISMISS'),
      ),
    ],
  );

  Widget _overviewPage() {
    final report = _report;
    final telemetry = report?.telemetry ?? const <String, dynamic>{};
    final coherence = _double(telemetry['coherence'], fallback: .994);
    final worlds =
        (telemetry['worlds'] as num?)?.toInt() ??
        int.tryParse(_worldsController.text) ??
        12000;
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _SectionHeading(
            eyebrow: 'CYBERFORGE 3 / AEGIS-816',
            title: 'Predict pressure before it becomes an incident.',
            subtitle:
                'Fuse identity, endpoint, API, cloud, human, vendor, route, and physical-security surfaces into one explainable defensive digital twin.',
            actions: <Widget>[
              FilledButton.icon(
                onPressed: _running ? null : _runScan,
                icon: _running
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow),
                label: Text(_running ? 'SIMULATING' : 'RUN SUPER SCAN'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final wide = constraints.maxWidth >= 820;
              final left = _Panel(
                child: Row(
                  children: <Widget>[
                    RiskArc(value: report?.overallRisk ?? .61),
                    const SizedBox(width: 22),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          _SignalLine(
                            label: 'TRUTH MODE',
                            value:
                                telemetry['truthLabel']?.toString() ??
                                'quantum-inspired conventional simulation',
                            color: CyberForgeColors.cyan,
                          ),
                          _SignalLine(
                            label: 'LOCAL LLAMA PASSES',
                            value: '${telemetry['localLlamaPasses'] ?? 0}',
                            color: CyberForgeColors.green,
                          ),
                          _SignalLine(
                            label: 'LOCAL GEMMA',
                            value: telemetry['localGemmaLoaded'] == true
                                ? 'LOADED'
                                : 'STANDBY',
                            color: telemetry['localGemmaLoaded'] == true
                                ? CyberForgeColors.green
                                : CyberForgeColors.amber,
                          ),
                          _SignalLine(
                            label: 'PACKET DIGEST',
                            value: report == null
                                ? 'not generated'
                                : _short(report.packetDigest),
                            color: CyberForgeColors.violet,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
              final right = GammaSimstationDisplay(
                coherence: coherence,
                worlds: worlds,
                active: _running || report != null,
              );
              return wide
                  ? Row(
                      // This row lives inside _PageScroll, whose vertical
                      // constraint is unbounded. Stretching here can leave
                      // the panel children without a usable height.
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: left),
                        const SizedBox(width: 16),
                        Expanded(child: right),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        left,
                        const SizedBox(height: 16),
                        right,
                      ],
                    );
            },
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'SURFACE PRESSURE MATRIX',
            subtitle:
                'Normalized blue-team planning pressure by defensive domain.',
            child: SurfaceMatrix(
              dimensions: report?.dimensions ?? _fallbackDimensions(),
            ),
          ),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final timeline = _Panel(
                title: 'TEMPORAL PRESSURE',
                subtitle:
                    'Local-hour simulation; not a forensic incident timestamp.',
                child: TimelineStrip(
                  timeline: report?.timeline ?? _fallbackTimeline(),
                ),
              );
              final impact = _ImpactPanel(report: report);
              return constraints.maxWidth >= 760
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(flex: 3, child: timeline),
                        const SizedBox(width: 16),
                        Expanded(flex: 2, child: impact),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        timeline,
                        const SizedBox(height: 16),
                        impact,
                      ],
                    );
            },
          ),
          if (report != null) ...<Widget>[
            const SizedBox(height: 16),
            _Panel(
              title: 'SIMULATION SYNTHESIS',
              child: Text(
                report.summary,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _scannerPage() {
    final surfaces =
        (_packet?['surfaces'] as List<dynamic>? ?? const <dynamic>[])
            .whereType<Map>()
            .map(_asMap)
            .toList(growable: false);
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _SectionHeading(
            eyebrow: 'NAZA-DERIVED SUPER SCANNER',
            title: 'Scan one surface or an entire operating system.',
            subtitle:
                'Coordinates are optional. Named places, abstract zones, routes, systems, teams, devices, APIs, and vendor relationships can all become simulated surfaces.',
          ),
          const SizedBox(height: 20),
          _Panel(
            title: 'SCAN ENVELOPE',
            child: Column(
              children: <Widget>[
                LayoutBuilder(
                  builder: (BuildContext context, BoxConstraints constraints) {
                    final fields = <Widget>[
                      TextField(
                        controller: _locationController,
                        decoration: const InputDecoration(
                          labelText: 'Named location or abstract zone',
                          prefixIcon: Icon(Icons.place),
                        ),
                      ),
                      TextField(
                        controller: _latitudeController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                          signed: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Latitude · optional',
                          prefixIcon: Icon(Icons.my_location),
                        ),
                      ),
                      TextField(
                        controller: _longitudeController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                          signed: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Longitude · optional',
                          prefixIcon: Icon(Icons.explore),
                        ),
                      ),
                      TextField(
                        controller: _worldsController,
                        keyboardType: TextInputType.number,
                        inputFormatters: <TextInputFormatter>[
                          FilteringTextInputFormatter.digitsOnly,
                        ],
                        decoration: const InputDecoration(
                          labelText: 'Monte Carlo worlds',
                          prefixIcon: Icon(Icons.all_inclusive),
                        ),
                      ),
                    ];
                    final columns = constraints.maxWidth >= 760
                        ? 4
                        : constraints.maxWidth >= 480
                        ? 2
                        : 1;
                    return GridView.count(
                      crossAxisCount: columns,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: columns == 1 ? 6 : 2.3,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      children: fields,
                    );
                  },
                ),
                const SizedBox(height: 14),
                Material(
                  color: Colors.transparent,
                  child: SwitchListTile.adaptive(
                    value: _includeRemote,
                    onChanged: (bool value) =>
                        setState(() => _includeRemote = value),
                    title: const Text('Use encrypted cloud model council'),
                    subtitle: const Text(
                      'Only redacted simulation packets leave the device. Provider keys stay in the local AES-GCM vault.',
                    ),
                    secondary: const Icon(Icons.cloud),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                Material(
                  color: Colors.transparent,
                  child: SwitchListTile.adaptive(
                    value: _includeNewsCapture,
                    onChanged: (bool value) =>
                        setState(() => _includeNewsCapture = value),
                    title: const Text(
                      'Opt in to external incident news capture',
                    ),
                    subtitle: const Text(
                      'Disabled by default. Requires an unlocked vault and a configured search provider; results remain labeled as external evidence.',
                    ),
                    secondary: const Icon(Icons.newspaper),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _running ? null : _runScan,
                    icon: const Icon(Icons.radar),
                    label: const Text('RUN AUTHORIZED DEFENSIVE SIMULATION'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'SURFACE INVENTORY · ${surfaces.length}',
            subtitle:
                'Each row is a modeled relationship, not a live scan target.',
            child: Column(
              children: surfaces
                  .map(
                    (Map<String, dynamic> surface) => _SurfaceRow(
                      surface: surface,
                      finding: _findingFor(surface['id']?.toString()),
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
          if (_report != null) ...<Widget>[
            const SizedBox(height: 16),
            _Panel(
              title: 'RANKED FINDINGS',
              child: Column(
                children: _report!.findings
                    .take(12)
                    .map(
                      (Map<String, dynamic> finding) =>
                          _FindingCard(finding: finding),
                    )
                    .toList(growable: false),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _simstationPage() {
    final telemetry = _report?.telemetry ?? const <String, dynamic>{};
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _SectionHeading(
            eyebrow: 'AEGIS-816',
            title: 'Dyson Sphere Gamma Simstation.',
            subtitle:
                'A deliberately labeled quantum-inspired scheduler: seeded, reproducible conventional computation with massive-world metaphors, not a claim of physical quantum hardware.',
          ),
          const SizedBox(height: 20),
          GammaSimstationDisplay(
            coherence: _double(telemetry['coherence'], fallback: .99621),
            worlds: (telemetry['worlds'] as num?)?.toInt() ?? 12000,
            active: _running || _report != null,
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'BOOTCOM',
            child: _TerminalBody(
              lines: _report?.bootcom ?? _fallbackBootcom(),
              height: 310,
            ),
          ),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final cards = <Widget>[
                _MetricCard(
                  icon: Icons.blur_circular,
                  label: 'REGISTER',
                  value: '${telemetry['simulatedQubits'] ?? 81611511}',
                  detail: 'simulated qubits',
                ),
                _MetricCard(
                  icon: Icons.filter_vintage,
                  label: 'OBSERVERS',
                  value: '${telemetry['observationFrames'] ?? 4096}',
                  detail: 'parallel frames',
                ),
                _MetricCard(
                  icon: Icons.speed,
                  label: 'RUN TIME',
                  value: '${telemetry['durationMs'] ?? 0} ms',
                  detail: 'last local run',
                ),
                _MetricCard(
                  icon: Icons.visibility_off,
                  label: 'REDACTIONS',
                  value: '${telemetry['redactions'] ?? 0}',
                  detail: 'before council',
                ),
              ];
              return GridView.count(
                crossAxisCount: constraints.maxWidth >= 760 ? 4 : 2,
                childAspectRatio: 1.35,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                children: cards,
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _councilPage() {
    final council = _report?.council ?? const <String, dynamic>{};
    final consensus = _asMap(council['consensus']);
    final opinions =
        (council['opinions'] as List<dynamic>? ?? const <dynamic>[])
            .whereType<Map>()
            .map(_asMap)
            .toList(growable: false);
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _SectionHeading(
            eyebrow: 'MULTI-MODEL DEFENSE COUNCIL',
            title: 'Independent perspectives. Visible disagreement.',
            subtitle:
                'Llama scans individual surfaces; Gemma synthesizes privately; GPT-5.6, Grok 4.5, Kimi K3, and Gemini can join through explicit, redacted, vault-authorized calls.',
          ),
          const SizedBox(height: 20),
          _Panel(
            title: 'MODEL FABRIC',
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: _health.council.isEmpty
                  ? _defaultModelChips()
                  : _health.council.map(_modelChip).toList(growable: false),
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'CONSENSUS',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  consensus['summary']?.toString() ??
                      'Run a simulation to generate council consensus.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 16),
                _TagWrap(
                  values:
                      (consensus['priorityVectors'] as List<dynamic>? ??
                              const <dynamic>[])
                          .map((dynamic value) => value.toString())
                          .toList(),
                ),
                const SizedBox(height: 14),
                _SignalLine(
                  label: 'DISAGREEMENT',
                  value:
                      '${(_double(consensus['disagreement']) * 100).toStringAsFixed(0)}%',
                  color: CyberForgeColors.amber,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (opinions.isEmpty)
            const _Panel(
              child: Text('No council opinions yet. Run the super scanner.'),
            )
          else
            ...opinions.map(
              (Map<String, dynamic> opinion) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _OpinionCard(opinion: opinion),
              ),
            ),
        ],
      ),
    );
  }

  Widget _vaultPage() {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _SectionHeading(
            eyebrow: 'CRYPTOGRAPHIC CONTROL PLANE',
            title: 'Keys belong to the vault, never the interface.',
            subtitle:
                'Record-level AES-256-GCM, Argon2id unlock, rotating data keys, secure-storage session tokens, encrypted local models, and optional ML-KEM hybrid recovery.',
          ),
          const SizedBox(height: 20),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final cards = <Widget>[
                _MetricCard(
                  icon: Icons.lock,
                  label: 'VAULT',
                  value: _health.vaultUnlocked ? 'UNLOCKED' : 'LOCKED',
                  detail: 'AES-256-GCM records',
                ),
                _MetricCard(
                  icon: Icons.security,
                  label: 'POST-QUANTUM',
                  value: _health.postQuantumAvailable
                      ? 'ML-KEM READY'
                      : 'OPTIONAL',
                  detail: 'hybrid recovery',
                ),
                _MetricCard(
                  icon: Icons.key,
                  label: 'PROVIDERS',
                  value:
                      '${_health.council.where((Map<String, dynamic> item) => item['configured'] == true).length}',
                  detail: 'configured models',
                ),
                _MetricCard(
                  icon: Icons.memory,
                  label: 'LOCAL MODELS',
                  value:
                      '${_health.models.where((Map<String, dynamic> item) => item['installed'] == true).length}',
                  detail: 'encrypted at rest',
                ),
              ];
              return GridView.count(
                crossAxisCount: constraints.maxWidth >= 760 ? 4 : 2,
                childAspectRatio: 1.35,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                children: cards,
              );
            },
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'VAULT OPERATIONS',
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                FilledButton.icon(
                  onPressed: () {
                    if (!_health.online) {
                      setState(
                        () => _error =
                            'CyberForge sidecar is offline. Start it with ./tool/run_dev.sh (port 8788), then press refresh.',
                      );
                      return;
                    }
                    _vaultPasswordDialog(create: !_health.vaultExists);
                  },
                  icon: Icon(
                    _health.vaultUnlocked ? Icons.lock_open : Icons.password,
                  ),
                  label: Text(
                    _health.vaultUnlocked
                        ? 'RE-UNLOCK'
                        : _health.vaultExists
                        ? 'UNLOCK EXISTING VAULT'
                        : 'CREATE VAULT',
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: _health.vaultUnlocked
                      ? _configureProviderDialog
                      : null,
                  icon: const Icon(Icons.vpn_key),
                  label: const Text('ADD PROVIDER KEY'),
                ),
                OutlinedButton.icon(
                  onPressed: _health.vaultUnlocked
                      ? () async {
                          await _client.rotateVaultKey();
                          await _refreshHealth();
                          _notice('Vault data key rotated.');
                        }
                      : null,
                  icon: const Icon(Icons.rotate_right),
                  label: const Text('ROTATE DATA KEY'),
                ),
                OutlinedButton.icon(
                  onPressed: _health.vaultUnlocked
                      ? () async {
                          try {
                            await _client.lockVault();
                            await _refreshHealth();
                          } on Object catch (error) {
                            if (mounted) {
                              setState(
                                () => _error =
                                    'Vault session expired. Restart the sidecar or unlock the vault again before locking it: $error',
                              );
                            }
                          }
                        }
                      : null,
                  icon: const Icon(Icons.lock),
                  label: const Text('LOCK'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'LOCAL MODEL INVENTORY',
            subtitle:
                'Pinned hashes are checked before encrypted installation.',
            child: Column(
              children:
                  (_health.models.isEmpty
                          ? _fallbackModelStatuses()
                          : _health.models)
                      .map(
                        (Map<String, dynamic> model) => _ModelRow(
                          model: model,
                          vaultUnlocked: _health.vaultUnlocked,
                          onInstall: () =>
                              _modelAction('install', model['id'].toString()),
                          onLoad: () =>
                              _modelAction('load', model['id'].toString()),
                          onUnload: () =>
                              _modelAction('unload', model['id'].toString()),
                        ),
                      )
                      .toList(growable: false),
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'SECURE PROVIDERS',
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                _ProviderTile(
                  name: 'OpenAI',
                  model: 'GPT-5.6',
                  icon: Icons.auto_awesome,
                ),
                _ProviderTile(name: 'xAI', model: 'Grok 4.5', icon: Icons.bolt),
                _ProviderTile(
                  name: 'DigitalOcean',
                  model: 'Kimi K3',
                  icon: Icons.water,
                ),
                _ProviderTile(
                  name: 'Google',
                  model: 'Gemini 3.6 Flash',
                  icon: Icons.diamond,
                ),
                _ProviderTile(
                  name: 'Local',
                  model: 'Gemma 4 E2B 4-bit',
                  icon: Icons.memory,
                ),
                _ProviderTile(
                  name: 'Local',
                  model: 'Llama 3 Small',
                  icon: Icons.radar,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _simcomPage() {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _SectionHeading(
            eyebrow: 'SIMCOM TERMINAL',
            title: 'Ask the digital twin, not a live target.',
            subtitle:
                'Commands return modeled ranges, assumptions, controls, and evidence needs. Real-world actor or country attribution remains disabled without verified forensic evidence.',
          ),
          const SizedBox(height: 20),
          _Panel(
            title: 'BOOTCOM QUICK COMMANDS',
            subtitle:
                'Use these safe local simulation commands to get oriented.',
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                for (final command in const <String>[
                  'help',
                  'bootcom',
                  'status',
                  'scan --worlds 12000',
                  'impact',
                  'council',
                ])
                  OutlinedButton(
                    onPressed: () {
                      _simcomController.text = command;
                      _sendSimcom();
                    },
                    child: Text(command.toUpperCase()),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            child: Column(
              children: <Widget>[
                _TerminalBody(
                  lines: _terminal,
                  height: 430,
                  controller: _terminalScroll,
                ),
                const SizedBox(height: 12),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: TextField(
                        controller: _simcomController,
                        onSubmitted: (_) => _sendSimcom(),
                        style: const TextStyle(fontFamily: 'monospace'),
                        decoration: const InputDecoration(
                          prefixText: '> ',
                          hintText:
                              'boot | status | scan | timeline | impact | hotspots | council | origin',
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    IconButton.filled(
                      onPressed: _sendSimcom,
                      icon: const Icon(Icons.send),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _modelDownloaderPage() {
    final models = _health.models.isEmpty
        ? _fallbackModelStatuses()
        : _health.models;
    final installed = models
        .where((model) => model['installed'] == true)
        .length;
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _SectionHeading(
            eyebrow: 'MODEL SUPPLY CHAIN',
            title: 'Download, verify, encrypt, and load local models.',
            subtitle:
                'Every model is pinned to a SHA-256 profile, streamed to a temporary file, verified, encrypted at rest, and only then made available to a runtime.',
          ),
          const SizedBox(height: 20),
          _Panel(
            title: 'DOWNLOADER CONTROL DECK',
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                FilledButton.icon(
                  onPressed: _health.vaultUnlocked
                      ? () async {
                          for (final model in models.where(
                            (model) => model['installed'] != true,
                          )) {
                            await _modelAction(
                              'install',
                              model['id'].toString(),
                            );
                          }
                        }
                      : null,
                  icon: const Icon(Icons.download),
                  label: Text('DOWNLOAD ALL (${models.length - installed})'),
                ),
                OutlinedButton.icon(
                  onPressed: _refreshHealth,
                  icon: const Icon(Icons.refresh),
                  label: const Text('REFRESH INVENTORY'),
                ),
                Chip(
                  avatar: Icon(
                    _health.vaultUnlocked ? Icons.verified_user : Icons.lock,
                    size: 18,
                  ),
                  label: Text(
                    _health.vaultUnlocked
                        ? 'Encrypted destination ready'
                        : 'Unlock vault to download',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            title: 'MODEL QUEUE',
            subtitle:
                'Pinned profile, runtime compatibility, integrity, and lifecycle controls.',
            child: Column(
              children: models
                  .map(
                    (model) => _ModelRow(
                      model: model,
                      vaultUnlocked: _health.vaultUnlocked,
                      onInstall: () =>
                          _modelAction('install', model['id'].toString()),
                      onLoad: () =>
                          _modelAction('load', model['id'].toString()),
                      onUnload: () =>
                          _modelAction('unload', model['id'].toString()),
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
        ],
      ),
    );
  }

  Widget _safetyPage() => const _PageScroll(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        _SectionHeading(
          eyebrow: 'NON-NEGOTIABLE BOUNDARY',
          title: 'Defense, rehearsal, and resilience only.',
          subtitle:
              'CyberForge models risk and safe validation. It does not create exploit payloads, phishing content, malware, persistence, evasion, credential theft, destructive actions, or physical-entry procedures.',
        ),
        SizedBox(height: 20),
        _Panel(
          title: 'ALLOWED',
          child: _SafetyList(
            color: CyberForgeColors.green,
            icon: Icons.check_circle,
            values: <String>[
              'Synthetic and owner-authorized digital twins',
              'Passive inventory and imported telemetry summaries',
              'Phishing susceptibility estimates without phishing copy',
              'Credential, API, cloud, endpoint, vendor, route, and physical-control risk modeling',
              'Recovery exercises, tabletop planning, control comparisons, and evidence checklists',
              'Uncertainty-aware time windows and equivalent impact ranges',
            ],
          ),
        ),
        SizedBox(height: 16),
        _Panel(
          title: 'BLOCKED',
          child: _SafetyList(
            color: CyberForgeColors.red,
            icon: Icons.block,
            values: <String>[
              'Live exploitation, weaponized payloads, or destructive automation',
              'Credential theft, session hijacking, persistence, or evasion instructions',
              'Deceptive phishing messages or impersonation workflows',
              'Physical bypass or unauthorized entry procedures',
              'Country, actor, or person attribution from weak simulated indicators',
              'Sending raw secrets, private logs, or sensitive identifiers to cloud models',
            ],
          ),
        ),
      ],
    ),
  );

  Widget _settingsPage() => _PageScroll(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const _SectionHeading(
          eyebrow: 'CONTROL PLANE SETTINGS',
          title: 'Explicit controls for external data and local models.',
          subtitle:
              'External news capture is off by default. Local model import verifies the pinned digest before encryption.',
        ),
        const SizedBox(height: 20),
        _Panel(
          title: 'SESSION STORAGE',
          child: Column(
            children: <Widget>[
              Material(
                color: Colors.transparent,
                child: SwitchListTile.adaptive(
                  value: _client.usesSystemKeyring,
                  onChanged: defaultTargetPlatform == TargetPlatform.linux
                      ? null
                      : (bool value) {
                          _client.setStorageMode(useSystemKeyring: value);
                          setState(() {});
                        },
                  title: const Text('Use system keyring for session tokens'),
                  subtitle: Text(
                    defaultTargetPlatform == TargetPlatform.linux
                        ? 'Unavailable in this Linux container; memory-only mode prevents libsecret crashes.'
                        : 'Stores only the short-lived sidecar session token in the operating system keyring.',
                  ),
                  secondary: Icon(
                    defaultTargetPlatform == TargetPlatform.linux
                        ? Icons.memory
                        : Icons.key,
                  ),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const Divider(),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Vault records and model encryption remain protected by the sidecar vault. This setting controls only the Flutter session token.',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _Panel(
          title: 'NEWS CAPTURE SAFETY',
          child: Column(
            children: <Widget>[
              Material(
                color: Colors.transparent,
                child: SwitchListTile.adaptive(
                  value: _includeNewsCapture,
                  onChanged: (bool value) =>
                      setState(() => _includeNewsCapture = value),
                  title: const Text('Enable external incident news capture'),
                  subtitle: const Text(
                    'Disabled by default. Requires an unlocked vault and a configured provider. Results are labeled external evidence.',
                  ),
                  secondary: const Icon(Icons.public),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const Divider(),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Search providers: xAI Grok 4.5 and OpenAI Responses web search.',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _Panel(
          title: 'LOCAL MODEL IMPORT',
          subtitle:
              'Choose an existing file already on this machine. The sidecar verifies its pinned SHA-256 and encrypts it into the model vault.',
          child: Column(
            children: <Widget>[
              TextField(
                controller: _localModelPathController,
                decoration: const InputDecoration(
                  labelText: 'Existing model file path',
                  hintText: '/path/to/model.gguf or .litertlm',
                  prefixIcon: Icon(Icons.folder_open),
                ),
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Select the target profile in Model Downloader, then use Import Local File there.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerLeft,
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children:
                      (_health.models.isEmpty
                              ? _fallbackModelStatuses()
                              : _health.models)
                          .map(
                            (model) => OutlinedButton.icon(
                              onPressed: _health.vaultUnlocked
                                  ? () async {
                                      try {
                                        await _client.importLocalModel(
                                          model['id'].toString(),
                                          _localModelPathController.text,
                                        );
                                        await _refreshHealth();
                                        _notice(
                                          'Local model verified and encrypted.',
                                        );
                                      } on Object catch (error) {
                                        setState(
                                          () => _error = error.toString(),
                                        );
                                      }
                                    }
                                  : null,
                              icon: const Icon(Icons.file_download),
                              label: Text(
                                'IMPORT ${model['name'] ?? model['id']}',
                              ),
                            ),
                          )
                          .toList(growable: false),
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );

  Map<String, dynamic>? _findingFor(String? id) {
    if (id == null || _report == null) return null;
    for (final finding in _report!.findings) {
      if (finding['id']?.toString() == id) return finding;
    }
    return null;
  }

  Future<void> _vaultPasswordDialog({required bool create}) async {
    final controller = TextEditingController();
    var createMode = create;
    final result = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, StateSetter setDialogState) =>
            AlertDialog(
              title: Text(
                createMode
                    ? 'Create encrypted vault'
                    : 'Unlock encrypted vault',
              ),
              content: SizedBox(
                width: 440,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    TextField(
                      controller: controller,
                      obscureText: true,
                      autofocus: true,
                      decoration: const InputDecoration(
                        labelText: 'Vault password · 12+ characters',
                        prefixIcon: Icon(Icons.password),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Material(
                      color: Colors.transparent,
                      child: SwitchListTile.adaptive(
                        value: createMode,
                        onChanged: (bool value) =>
                            setDialogState(() => createMode = value),
                        title: const Text('Create a new vault'),
                        subtitle: const Text(
                          'Turn off to unlock an existing vault.',
                        ),
                        contentPadding: EdgeInsets.zero,
                      ),
                    ),
                  ],
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('CANCEL'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: Text(createMode ? 'CREATE' : 'UNLOCK'),
                ),
              ],
            ),
      ),
    );
    if (result != true) {
      controller.dispose();
      return;
    }
    try {
      if (createMode) {
        await _client.createVault(controller.text);
      } else {
        await _client.unlockVault(controller.text);
      }
      await _refreshHealth();
      _notice(createMode ? 'Encrypted vault created.' : 'Vault unlocked.');
    } on Object catch (error) {
      setState(() => _error = error.toString());
    } finally {
      controller.dispose();
    }
  }

  Future<void> _configureProviderDialog() async {
    var provider = 'openai';
    final secretController = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, StateSetter setDialogState) => AlertDialog(
          title: const Text('Store provider key'),
          content: SizedBox(
            width: 460,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                DropdownButtonFormField<String>(
                  initialValue: provider,
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(
                      value: 'openai',
                      child: Text('OpenAI · GPT-5.6'),
                    ),
                    DropdownMenuItem(
                      value: 'xai',
                      child: Text('xAI · Grok 4.5'),
                    ),
                    DropdownMenuItem(
                      value: 'digitalocean',
                      child: Text('DigitalOcean · Kimi K3'),
                    ),
                    DropdownMenuItem(
                      value: 'gemini',
                      child: Text('Google · Gemini API'),
                    ),
                  ],
                  onChanged: (String? value) {
                    if (value != null) setDialogState(() => provider = value);
                  },
                  decoration: const InputDecoration(labelText: 'Provider'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: secretController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'API key or access token',
                    prefixIcon: Icon(Icons.vpn_key),
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'The secret is sent only to the loopback sidecar and immediately encrypted into the local vault. It is never placed in scenario JSON or logs.',
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('CANCEL'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('ENCRYPT & STORE'),
            ),
          ],
        ),
      ),
    );
    try {
      if (accepted == true && secretController.text.trim().isNotEmpty) {
        await _client.setProviderSecret(provider, secretController.text.trim());
        await _refreshHealth();
        _notice('$provider key stored in the encrypted vault.');
      }
    } on Object catch (error) {
      setState(() => _error = error.toString());
    } finally {
      secretController.dispose();
    }
  }

  Future<void> _modelAction(String action, String id) async {
    try {
      switch (action) {
        case 'install':
          _notice('Downloading, verifying, and encrypting $id.');
          await _client.installModel(id);
          break;
        case 'load':
          await _client.loadModel(id);
          break;
        case 'unload':
          await _client.unloadModel(id);
          break;
      }
      await _refreshHealth();
    } on Object catch (error) {
      setState(() => _error = error.toString());
    }
  }

  void _notice(String value) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  List<Widget> _defaultModelChips() => <Widget>[
    _modelChip(<String, dynamic>{
      'provider': 'local',
      'model': 'llama3-small-q3',
      'configured': false,
    }),
    _modelChip(<String, dynamic>{
      'provider': 'local',
      'model': 'gemma4-e2b-litert-4bit',
      'configured': false,
    }),
    _modelChip(<String, dynamic>{
      'provider': 'openai',
      'model': 'gpt-5.6',
      'configured': false,
    }),
    _modelChip(<String, dynamic>{
      'provider': 'xai',
      'model': 'grok-4.5',
      'configured': false,
    }),
    _modelChip(<String, dynamic>{
      'provider': 'digitalocean',
      'model': 'kimi-k3',
      'configured': false,
    }),
    _modelChip(<String, dynamic>{
      'provider': 'gemini',
      'model': 'gemini-3.6-flash',
      'configured': false,
    }),
    _modelChip(<String, dynamic>{
      'provider': 'offline',
      'model': 'policy-calibrator-v3',
      'configured': true,
    }),
  ];

  Widget _modelChip(Map<String, dynamic> value) {
    final configured = value['configured'] == true;
    return Chip(
      avatar: Icon(
        configured ? Icons.check_circle : Icons.radio_button_unchecked,
        color: configured ? CyberForgeColors.green : CyberForgeColors.muted,
        size: 18,
      ),
      label: Text('${value['provider']} / ${value['model']}'),
      side: BorderSide(
        color: configured ? CyberForgeColors.green : CyberForgeColors.grid,
      ),
      backgroundColor: CyberForgeColors.surfaceRaised,
    );
  }

  static String _pageTitle(int index) => const <String>[
    'Command Overview',
    'Super Scanner',
    'Gamma Simstation',
    'Model Council',
    'Vault & Models',
    'Model Downloader',
    'SIMCOM Terminal',
    'Safety Boundary',
    'Settings',
  ][index];
}

final class _PageScroll extends StatelessWidget {
  const _PageScroll({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: const EdgeInsets.all(24),
    child: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1280),
        child: child,
      ),
    ),
  );
}

final class _Brand extends StatelessWidget {
  const _Brand({this.compact = false});
  final bool compact;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: <Widget>[
      Container(
        width: compact ? 34 : 42,
        height: compact ? 34 : 42,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: <Color>[CyberForgeColors.cyan, CyberForgeColors.violet],
          ),
          borderRadius: BorderRadius.circular(12),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: CyberForgeColors.cyan.withValues(alpha: .20),
              blurRadius: 20,
            ),
          ],
        ),
        child: const Icon(Icons.fingerprint, color: Color(0xFF07101D)),
      ),
      const SizedBox(width: 11),
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            'CYBERFORGE',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
              letterSpacing: 1.2,
            ),
          ),
          if (!compact)
            Text(
              'DEFENSIVE INTELLIGENCE SYSTEM',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: CyberForgeColors.muted,
                letterSpacing: .7,
              ),
            ),
        ],
      ),
    ],
  );
}

final class _ConnectionPill extends StatelessWidget {
  const _ConnectionPill({required this.health});
  final CyberForgeHealth health;

  @override
  Widget build(BuildContext context) {
    final color = health.online
        ? CyberForgeColors.green
        : CyberForgeColors.amber;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: .55)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 7),
          Text(
            health.online ? 'SIDECAR ${health.version}' : 'OFFLINE MODE',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w800,
              letterSpacing: .6,
            ),
          ),
        ],
      ),
    );
  }
}

final class _SectionHeading extends StatelessWidget {
  const _SectionHeading({
    required this.eyebrow,
    required this.title,
    required this.subtitle,
    this.actions = const <Widget>[],
  });

  final String eyebrow;
  final String title;
  final String subtitle;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.spaceBetween,
    crossAxisAlignment: WrapCrossAlignment.end,
    spacing: 20,
    runSpacing: 14,
    children: <Widget>[
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 820),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              eyebrow,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: CyberForgeColors.cyan,
                fontWeight: FontWeight.w900,
                letterSpacing: 1.6,
              ),
            ),
            const SizedBox(height: 8),
            Text(title, style: Theme.of(context).textTheme.headlineLarge),
            const SizedBox(height: 9),
            Text(
              subtitle,
              style: Theme.of(
                context,
              ).textTheme.bodyLarge?.copyWith(color: CyberForgeColors.muted),
            ),
          ],
        ),
      ),
      if (actions.isNotEmpty)
        Row(mainAxisSize: MainAxisSize.min, children: actions),
    ],
  );
}

final class _Panel extends StatelessWidget {
  const _Panel({this.title, this.subtitle, required this.child});
  final String? title;
  final String? subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: CyberForgeColors.surface.withValues(alpha: .91),
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: CyberForgeColors.grid),
      boxShadow: <BoxShadow>[
        BoxShadow(
          color: Colors.black.withValues(alpha: .20),
          blurRadius: 26,
          offset: const Offset(0, 12),
        ),
      ],
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        if (title != null) ...<Widget>[
          Text(
            title!,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
              letterSpacing: .6,
            ),
          ),
          if (subtitle != null) ...<Widget>[
            const SizedBox(height: 3),
            Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
          ],
          const SizedBox(height: 15),
        ],
        child,
      ],
    ),
  );
}

final class _SignalLine extends StatelessWidget {
  const _SignalLine({
    required this.label,
    required this.value,
    required this.color,
  });
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Row(
      children: <Widget>[
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 116,
          child: Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: CyberForgeColors.muted,
              fontWeight: FontWeight.w800,
              letterSpacing: .7,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    ),
  );
}

final class _ImpactPanel extends StatelessWidget {
  const _ImpactPanel({required this.report});
  final ScanReport? report;

  @override
  Widget build(BuildContext context) {
    final impact = report?.impact ?? const <String, dynamic>{};
    final range = _asMap(impact['affectedEquivalentRange']);
    final percent = _asMap(impact['affectedEquivalentPercent']);
    return _Panel(
      title: 'EQUIVALENT IMPACT RANGE',
      subtitle: 'Loss of trustworthy operation; not confirmed malware count.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _BigValue(
            value: '${range['median'] ?? '—'}',
            label: 'MEDIAN AFFECTED EQUIVALENT',
          ),
          const SizedBox(height: 13),
          Row(
            children: <Widget>[
              Expanded(
                child: _MiniValue(
                  label: 'P05',
                  value: '${range['low'] ?? '—'}',
                ),
              ),
              Expanded(
                child: _MiniValue(
                  label: 'P95',
                  value: '${range['high'] ?? '—'}',
                ),
              ),
              Expanded(
                child: _MiniValue(
                  label: 'MEDIAN %',
                  value: percent['median'] == null
                      ? '—'
                      : '${(_double(percent['median']) * 100).toStringAsFixed(1)}%',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

final class _BigValue extends StatelessWidget {
  const _BigValue({required this.value, required this.label});
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: <Widget>[
      Text(
        value,
        style: Theme.of(context).textTheme.headlineLarge?.copyWith(
          color: CyberForgeColors.cyan,
          fontWeight: FontWeight.w900,
        ),
      ),
      Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
          color: CyberForgeColors.muted,
          letterSpacing: .8,
        ),
      ),
    ],
  );
}

final class _MiniValue extends StatelessWidget {
  const _MiniValue({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: <Widget>[
      Text(
        value,
        style: Theme.of(
          context,
        ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
      ),
      Text(
        label,
        style: Theme.of(
          context,
        ).textTheme.labelSmall?.copyWith(color: CyberForgeColors.muted),
      ),
    ],
  );
}

final class _SurfaceRow extends StatelessWidget {
  const _SurfaceRow({required this.surface, required this.finding});
  final Map<String, dynamic> surface;
  final Map<String, dynamic>? finding;

  @override
  Widget build(BuildContext context) {
    final risk = _double(finding?['risk']);
    final color = risk > .55
        ? CyberForgeColors.red
        : risk > .3
        ? CyberForgeColors.amber
        : CyberForgeColors.green;
    return Container(
      margin: const EdgeInsets.only(bottom: 9),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: CyberForgeColors.surfaceRaised.withValues(alpha: .62),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: CyberForgeColors.grid),
      ),
      child: Row(
        children: <Widget>[
          Icon(_surfaceIcon(surface['kind']?.toString()), color: color),
          const SizedBox(width: 12),
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  surface['label']?.toString() ?? 'Surface',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                Text(
                  '${surface['kind']} · ${surface['location']}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          Expanded(
            flex: 2,
            child: Wrap(
              spacing: 5,
              runSpacing: 5,
              children:
                  (surface['signals'] as List<dynamic>? ?? const <dynamic>[])
                      .take(2)
                      .map((dynamic value) => _TinyTag(value.toString()))
                      .toList(growable: false),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 80,
            child: Text(
              finding == null ? 'UNSCANNED' : '${(risk * 100).round()} RISK',
              textAlign: TextAlign.end,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

final class _FindingCard extends StatelessWidget {
  const _FindingCard({required this.finding});
  final Map<String, dynamic> finding;

  @override
  Widget build(BuildContext context) {
    final risk = _double(finding['risk']);
    final confidence = _double(finding['confidence']);
    final color = risk > .55
        ? CyberForgeColors.red
        : risk > .3
        ? CyberForgeColors.amber
        : CyberForgeColors.green;
    return ExpansionTile(
      tilePadding: const EdgeInsets.symmetric(horizontal: 4),
      leading: CircleAvatar(
        backgroundColor: color.withValues(alpha: .12),
        child: Text(
          '${(risk * 100).round()}',
          style: TextStyle(color: color, fontWeight: FontWeight.w900),
        ),
      ),
      title: Text(finding['label']?.toString() ?? 'Finding'),
      subtitle: Text(
        '${finding['kind']} · ${(confidence * 100).toStringAsFixed(0)}% confidence',
      ),
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Likely planning window: ${finding['likely_window'] ?? finding['likelyWindow'] ?? 'continuous'}',
              ),
              const SizedBox(height: 8),
              _TagWrap(
                values: _strings(
                  finding['priority_dimensions'] ??
                      finding['priorityDimensions'],
                ),
              ),
              const SizedBox(height: 10),
              ..._strings(finding['controls']).map(
                (String value) =>
                    _Bullet(value: value, color: CyberForgeColors.green),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

final class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.detail,
  });
  final IconData icon;
  final String label;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) => _Panel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        Icon(icon, color: CyberForgeColors.cyan),
        const SizedBox(height: 18),
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: CyberForgeColors.muted,
            letterSpacing: .8,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
        ),
        Text(detail, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );
}

final class _OpinionCard extends StatelessWidget {
  const _OpinionCard({required this.opinion});
  final Map<String, dynamic> opinion;

  @override
  Widget build(BuildContext context) {
    final succeeded = opinion['succeeded'] == true;
    return _Panel(
      title: '${opinion['provider']} / ${opinion['model']}',
      subtitle: succeeded
          ? '${opinion['latency_ms'] ?? opinion['latencyMs'] ?? 0} ms · uncertainty ${(_double(opinion['uncertainty']) * 100).toStringAsFixed(0)}%'
          : 'Model call failed safely',
      child: succeeded
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(opinion['summary']?.toString() ?? ''),
                const SizedBox(height: 10),
                _TagWrap(
                  values: _strings(
                    opinion['priority_vectors'] ?? opinion['priorityVectors'],
                  ),
                ),
                const SizedBox(height: 10),
                ..._strings(opinion['controls'])
                    .take(4)
                    .map(
                      (String value) =>
                          _Bullet(value: value, color: CyberForgeColors.green),
                    ),
              ],
            )
          : Text(opinion['error']?.toString() ?? 'Unknown provider error'),
    );
  }
}

final class _ModelRow extends StatelessWidget {
  const _ModelRow({
    required this.model,
    required this.vaultUnlocked,
    required this.onInstall,
    required this.onLoad,
    required this.onUnload,
  });

  final Map<String, dynamic> model;
  final bool vaultUnlocked;
  final VoidCallback onInstall;
  final VoidCallback onLoad;
  final VoidCallback onUnload;

  @override
  Widget build(BuildContext context) {
    final installed = model['installed'] == true;
    final loaded = model['loaded'] == true;
    return Material(
      color: Colors.transparent,
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(vertical: 5),
        leading: CircleAvatar(
          backgroundColor:
              (loaded ? CyberForgeColors.green : CyberForgeColors.cyan)
                  .withValues(alpha: .12),
          child: Icon(
            Icons.memory,
            color: loaded ? CyberForgeColors.green : CyberForgeColors.cyan,
          ),
        ),
        title: Text(
          model['name']?.toString() ?? model['id']?.toString() ?? 'Local model',
        ),
        subtitle: Text(
          '${model['runtime']} · ${installed ? 'encrypted at rest' : 'not installed'}\nSHA-256 ${_short(model['expected_sha256']?.toString() ?? model['expectedSha256']?.toString() ?? '')}',
        ),
        isThreeLine: true,
        trailing: Wrap(
          spacing: 6,
          children: <Widget>[
            if (!installed)
              IconButton(
                tooltip: 'Install securely',
                onPressed: vaultUnlocked ? onInstall : null,
                icon: const Icon(Icons.download),
              ),
            if (installed && !loaded)
              IconButton(
                tooltip: 'Decrypt and load',
                onPressed: vaultUnlocked ? onLoad : null,
                icon: const Icon(Icons.play_arrow),
              ),
            if (loaded)
              IconButton(
                tooltip: 'Unload and wipe temporary file',
                onPressed: onUnload,
                icon: const Icon(Icons.stop),
              ),
          ],
        ),
      ),
    );
  }
}

final class _ProviderTile extends StatelessWidget {
  const _ProviderTile({
    required this.name,
    required this.model,
    required this.icon,
  });
  final String name;
  final String model;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
    width: 220,
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: CyberForgeColors.surfaceRaised,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: CyberForgeColors.grid),
    ),
    child: Row(
      children: <Widget>[
        Icon(icon, color: CyberForgeColors.cyan),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                name,
                style: Theme.of(
                  context,
                ).textTheme.labelSmall?.copyWith(color: CyberForgeColors.muted),
              ),
              Text(
                model,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

final class _TerminalBody extends StatelessWidget {
  const _TerminalBody({
    required this.lines,
    required this.height,
    this.controller,
  });
  final List<String> lines;
  final double height;
  final ScrollController? controller;

  @override
  Widget build(BuildContext context) => Container(
    height: height,
    width: double.infinity,
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: const Color(0xFF03060B),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: CyberForgeColors.grid),
    ),
    child: ListView.builder(
      controller: controller,
      itemCount: lines.length,
      itemBuilder: (BuildContext context, int index) => SelectableText(
        lines[index],
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 12.5,
          height: 1.45,
          color: lines[index].startsWith('[ERROR]')
              ? CyberForgeColors.red
              : lines[index].startsWith('>')
              ? CyberForgeColors.cyan
              : CyberForgeColors.green,
        ),
      ),
    ),
  );
}

final class _TagWrap extends StatelessWidget {
  const _TagWrap({required this.values});
  final List<String> values;

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 7,
    runSpacing: 7,
    children: values
        .map((String value) => _TinyTag(value))
        .toList(growable: false),
  );
}

final class _TinyTag extends StatelessWidget {
  const _TinyTag(this.value);
  final String value;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
    decoration: BoxDecoration(
      color: CyberForgeColors.blue.withValues(alpha: .10),
      borderRadius: BorderRadius.circular(999),
      border: Border.all(color: CyberForgeColors.blue.withValues(alpha: .35)),
    ),
    child: Text(
      value,
      style: Theme.of(
        context,
      ).textTheme.labelSmall?.copyWith(color: CyberForgeColors.cyan),
    ),
  );
}

final class _Bullet extends StatelessWidget {
  const _Bullet({required this.value, required this.color});
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Container(
            width: 5,
            height: 5,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
        ),
        const SizedBox(width: 9),
        Expanded(child: Text(value)),
      ],
    ),
  );
}

final class _SafetyList extends StatelessWidget {
  const _SafetyList({
    required this.color,
    required this.icon,
    required this.values,
  });
  final Color color;
  final IconData icon;
  final List<String> values;

  @override
  Widget build(BuildContext context) => Column(
    children: values
        .map(
          (String value) => Material(
            color: Colors.transparent,
            child: ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(icon, color: color),
              title: Text(value),
            ),
          ),
        )
        .toList(growable: false),
  );
}

IconData _surfaceIcon(String? kind) =>
    <String, IconData>{
      'identity': Icons.key,
      'credential': Icons.password,
      'endpoint': Icons.devices,
      'server': Icons.dns,
      'api': Icons.api,
      'cloud': Icons.cloud,
      'facility': Icons.badge,
      'route': Icons.route,
      'vendor': Icons.handshake,
      'human': Icons.groups,
      'data': Icons.storage,
      'network': Icons.hub,
    }[kind] ??
    Icons.blur_on;

Map<String, dynamic> _asMap(Object? value) => value is Map
    ? value.map((dynamic key, dynamic item) => MapEntry(key.toString(), item))
    : <String, dynamic>{};

double _double(Object? value, {double fallback = 0}) => value is num
    ? value.toDouble()
    : double.tryParse(value?.toString() ?? '') ?? fallback;

String _short(String value) => value.length <= 18
    ? value
    : '${value.substring(0, 9)}…${value.substring(value.length - 7)}';

List<String> _strings(Object? value) => value is List
    ? value.map((dynamic item) => item.toString()).toList(growable: false)
    : const <String>[];

Map<String, dynamic> _fallbackDimensions() => <String, dynamic>{
  'credential': .82,
  'phishing': .77,
  'endpoint': .68,
  'api': .73,
  'cloud': .58,
  'physical': .64,
  'vendor': .79,
  'availability': .62,
  'data': .71,
};

List<Map<String, dynamic>> _fallbackTimeline() =>
    List<Map<String, dynamic>>.generate(
      24,
      (int hour) => <String, dynamic>{
        'hour': hour,
        'pressure': hour >= 8 && hour <= 18
            ? .48 + (hour % 5) * .11
            : .24 + (hour % 4) * .08,
      },
    );

List<String> _fallbackBootcom() => const <String>[
  'SIMCOM ACTIVE // DEFENSIVE DIGITAL TWIN // LOCAL-FIRST',
  '[00:00:00.000] Safety kernel: defense-only policy locked',
  '[00:00:00.041] Gamma coherence fabric: simulated',
  '[00:00:00.112] Logical register: 81,611,511 simulated qubits',
  '[00:00:00.189] Monte Carlo scheduler: ready',
  '[00:00:00.267] Surface graph: identity / endpoint / API / cloud / physical / vendor',
  '[00:00:00.341] Local Llama micro-scanner: standby',
  '[00:00:00.418] Local Gemma private synthesizer: standby',
  '[00:00:00.502] AES-256-GCM vault boundary: armed',
  '[00:00:00.589] ML-KEM recovery boundary: capability check complete',
  '[00:00:00.712] Live exploitation and attribution shortcuts: disabled',
  '[00:00:00.799] BOOT COMPLETE',
];

List<Map<String, dynamic>> _fallbackModelStatuses() => <Map<String, dynamic>>[
  <String, dynamic>{
    'id': 'gemma4-e2b-litert-4bit',
    'name': 'Gemma 4 E2B LiteRT-LM 4-bit',
    'runtime': 'litert_lm',
    'installed': false,
    'loaded': false,
    'expectedSha256':
        'ab7838cdfc8f77e54d8ca45eadceb20452d9f01e4bfade03e5dce27911b27e42',
  },
  <String, dynamic>{
    'id': 'llama3-small-q3',
    'name': 'Llama 3 Small Q3_K_M',
    'runtime': 'llama_cpp',
    'installed': false,
    'loaded': false,
    'expectedSha256':
        '8e4f4856fb84bafb895f1eb08e6c03e4be613ead2d942f91561aeac742a619aa',
  },
];

Map<String, dynamic> _fallbackPacket() => <String, dynamic>{
  'name': 'Synthetic Multisite Operations Twin',
  'description':
      'Authorized defensive simulation across cyber, human, vendor, route, and physical surfaces.',
  'authorization': <String, dynamic>{
    'authorized': true,
    'statement':
        'I own or am explicitly authorized to simulate every synthetic surface in this scenario.',
    'scope': 'Synthetic multisite operations digital twin',
    'synthetic': true,
  },
  'location': <String, dynamic>{
    'name': 'Named region only',
    'latitude': null,
    'longitude': null,
  },
  'worlds': 12000,
  'seed': 3923929,
  'includeRemoteModels': false,
  'surfaces': <Map<String, dynamic>>[
    <String, dynamic>{
      'id': 'identity-workforce',
      'label': 'Workforce identity plane',
      'kind': 'identity',
      'location': 'All sites',
      'criticality': .94,
      'exposure': .62,
      'controlStrength': .64,
      'humanPressure': .73,
      'telemetryConfidence': .82,
      'inventoryCount': 1600,
      'signals': <String>[
        'mixed MFA coverage',
        'high external contact',
        'password reset volume',
      ],
    },
    <String, dynamic>{
      'id': 'remote-access',
      'label': 'Remote access gateway',
      'kind': 'api',
      'location': 'Primary edge',
      'criticality': .96,
      'exposure': .78,
      'controlStrength': .70,
      'humanPressure': .48,
      'telemetryConfidence': .88,
      'inventoryCount': 12,
      'signals': <String>[
        'internet-facing',
        'vendor support sessions',
        'conditional access gaps',
      ],
    },
    <String, dynamic>{
      'id': 'endpoint-fleet',
      'label': 'Managed endpoint fleet',
      'kind': 'endpoint',
      'location': 'Distributed sites',
      'criticality': .86,
      'exposure': .56,
      'controlStrength': .72,
      'humanPressure': .59,
      'telemetryConfidence': .75,
      'inventoryCount': 4800,
      'signals': <String>[
        'coverage drift',
        'legacy applications',
        'shared workstations',
      ],
    },
    <String, dynamic>{
      'id': 'cloud-control',
      'label': 'Cloud control plane',
      'kind': 'cloud',
      'location': 'Cloud region',
      'criticality': .98,
      'exposure': .51,
      'controlStrength': .77,
      'humanPressure': .42,
      'telemetryConfidence': .86,
      'inventoryCount': 240,
      'signals': <String>[
        'service principals',
        'privileged automation',
        'cross-account trust',
      ],
    },
    <String, dynamic>{
      'id': 'visitor-access',
      'label': 'Visitor and delivery access',
      'kind': 'facility',
      'location': 'Public entrances',
      'criticality': .70,
      'exposure': .68,
      'controlStrength': .58,
      'humanPressure': .81,
      'telemetryConfidence': .69,
      'inventoryCount': 18,
      'signals': <String>[
        'shift changes',
        'temporary badges',
        'delivery congestion',
      ],
    },
    <String, dynamic>{
      'id': 'vendor-mesh',
      'label': 'Third-party support mesh',
      'kind': 'vendor',
      'location': 'External',
      'criticality': .88,
      'exposure': .67,
      'controlStrength': .55,
      'humanPressure': .52,
      'telemetryConfidence': .61,
      'inventoryCount': 74,
      'signals': <String>[
        'standing access',
        'shared support channels',
        'uneven assurance',
      ],
    },
  ],
};
