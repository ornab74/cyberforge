import 'dart:convert';

import 'package:flutter/material.dart';

import '../domain/models.dart';
import '../engine/simulation_engine.dart';
import '../llm/gemma_local_adapter.dart';
import '../llm/gemini_adapter.dart';
import '../llm/llm_adapter.dart';
import '../llm/model_council.dart';
import '../llm/offline_policy_adapter.dart';
import '../llm/openai_responses_adapter.dart';
import '../llm/xai_responses_adapter.dart';
import '../repository/scenario_repository.dart';
import '../theme/cyberforge_theme.dart';
import 'widgets/attack_surface_map.dart';
import 'widgets/risk_meter.dart';

final class CyberForgeHome extends StatefulWidget {
  const CyberForgeHome({super.key});

  @override
  State<CyberForgeHome> createState() => _CyberForgeHomeState();
}

final class _CyberForgeHomeState extends State<CyberForgeHome> {
  final _scenarioRepository = const ScenarioRepository();
  final _simulationEngine = const SimulationEngine();
  late final SimulationScenario _scenario;
  late final List<LlmAdapter> _adapters;
  SimulationReport? _report;
  CouncilReport? _council;
  var _selectedIndex = 0;
  var _running = false;
  var _councilRunning = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _scenario = _scenarioRepository.demo();
    _adapters = <LlmAdapter>[
      const OfflinePolicyAdapter(),
      OpenAiResponsesAdapter(),
      XaiResponsesAdapter(),
      GeminiAdapter(),
      GemmaLocalAdapter(),
    ];
    _runSimulation();
  }

  Future<void> _runSimulation() async {
    setState(() {
      _running = true;
      _error = null;
      _council = null;
    });
    try {
      final report = await _simulationEngine.run(_scenario, iterations: 6000);
      if (!mounted) return;
      setState(() => _report = report);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _runCouncil() async {
    final report = _report;
    if (report == null) return;
    setState(() {
      _councilRunning = true;
      _error = null;
    });
    try {
      final council = await ModelCouncil(adapters: _adapters).deliberate(
        scenario: _scenario,
        report: report,
      );
      if (!mounted) return;
      setState(() => _council = council);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _councilRunning = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 920;
        if (wide) {
          return Scaffold(
            body: Row(
              children: <Widget>[
                _Navigation(
                  selectedIndex: _selectedIndex,
                  onSelected: (value) => setState(() => _selectedIndex = value),
                ),
                const VerticalDivider(width: 1),
                Expanded(child: _page()),
              ],
            ),
          );
        }
        return Scaffold(
          appBar: AppBar(
            title: const _Brand(compact: true),
            backgroundColor: CyberForgeColors.surface,
          ),
          body: _page(),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _selectedIndex,
            onDestinationSelected: (value) =>
                setState(() => _selectedIndex = value),
            destinations: const <NavigationDestination>[
              NavigationDestination(icon: Icon(Icons.radar), label: 'Overview'),
              NavigationDestination(icon: Icon(Icons.hub), label: 'Surface'),
              NavigationDestination(icon: Icon(Icons.psychology), label: 'Council'),
              NavigationDestination(icon: Icon(Icons.policy), label: 'Safety'),
            ],
          ),
        );
      },
    );
  }

  Widget _page() {
    return SafeArea(
      child: Column(
        children: <Widget>[
          if (_error != null)
            MaterialBanner(
              content: Text(_error!),
              actions: <Widget>[
                TextButton(
                  onPressed: () => setState(() => _error = null),
                  child: const Text('Dismiss'),
                ),
              ],
            ),
          Expanded(
            child: IndexedStack(
              index: _selectedIndex,
              children: <Widget>[
                _OverviewPage(
                  scenario: _scenario,
                  report: _report,
                  running: _running,
                  onRun: _runSimulation,
                ),
                _SurfacePage(scenario: _scenario, report: _report),
                _CouncilPage(
                  adapters: _adapters,
                  council: _council,
                  running: _councilRunning,
                  enabled: _report != null,
                  onRun: _runCouncil,
                ),
                _SafetyPage(scenario: _scenario),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

final class _Navigation extends StatelessWidget {
  const _Navigation({required this.selectedIndex, required this.onSelected});

  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return NavigationRail(
      extended: true,
      selectedIndex: selectedIndex,
      onDestinationSelected: onSelected,
      leading: const Padding(
        padding: EdgeInsets.fromLTRB(14, 20, 14, 24),
        child: _Brand(),
      ),
      destinations: const <NavigationRailDestination>[
        NavigationRailDestination(
          icon: Icon(Icons.radar),
          selectedIcon: Icon(Icons.radar),
          label: Text('Command overview'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.hub_outlined),
          selectedIcon: Icon(Icons.hub),
          label: Text('Attack surface'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.psychology_outlined),
          selectedIcon: Icon(Icons.psychology),
          label: Text('Model council'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.policy_outlined),
          selectedIcon: Icon(Icons.policy),
          label: Text('Safety boundary'),
        ),
      ],
    );
  }
}

final class _Brand extends StatelessWidget {
  const _Brand({this.compact = false});
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(11),
            gradient: const LinearGradient(
              colors: <Color>[
                CyberForgeColors.blue,
                CyberForgeColors.violet,
              ],
            ),
          ),
          child: const Icon(Icons.shield_outlined, color: Colors.white),
        ),
        const SizedBox(width: 10),
        Text(
          compact ? 'CyberForge' : 'CYBERFORGE',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                letterSpacing: compact ? 0 : 1.7,
                fontSize: compact ? 19 : 16,
              ),
        ),
      ],
    );
  }
}

final class _OverviewPage extends StatelessWidget {
  const _OverviewPage({
    required this.scenario,
    required this.report,
    required this.running,
    required this.onRun,
  });

  final SimulationScenario scenario;
  final SimulationReport? report;
  final bool running;
  final VoidCallback onRun;

  @override
  Widget build(BuildContext context) {
    return _PageShell(
      title: 'Defense simulation command center',
      subtitle:
          'Predict where controls may fail, when pressure is highest, and which defensive changes reduce risk first.',
      actions: <Widget>[
        FilledButton.icon(
          onPressed: running ? null : onRun,
          icon: running
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.play_arrow),
          label: Text(running ? 'Simulating worlds…' : 'Run 6,000 worlds'),
        ),
      ],
      child: report == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: EdgeInsets.zero,
              children: <Widget>[
                _MetricsRow(report: report!),
                const SizedBox(height: 18),
                _ResponsivePair(
                  first: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          const _SectionTitle(
                            icon: Icons.auto_graph,
                            title: 'Primary prediction',
                          ),
                          const SizedBox(height: 14),
                          Text(
                            scenario.name,
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                  color: CyberForgeColors.cyan,
                                ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            report!.defensiveSummary,
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                          const SizedBox(height: 18),
                          _LocationHotspots(report: report!),
                        ],
                      ),
                    ),
                  ),
                  second: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          const _SectionTitle(
                            icon: Icons.memory,
                            title: 'Gamma fabric telemetry',
                          ),
                          const SizedBox(height: 16),
                          _TelemetryLine(
                            label: 'Simulated register',
                            value: report!.telemetry.simulatedQubitRegister
                                .toString(),
                          ),
                          _TelemetryLine(
                            label: 'Parallel worlds',
                            value: report!.telemetry.parallelWorlds.toString(),
                          ),
                          _TelemetryLine(
                            label: 'Coherence',
                            value:
                                '${(report!.telemetry.coherence * 100).toStringAsFixed(2)}%',
                          ),
                          _TelemetryLine(
                            label: 'Iterations',
                            value: report!.telemetry.iterations.toString(),
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'Quantum-inspired software simulation. No physical quantum computer or Dyson-sphere hardware is claimed.',
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        const _SectionTitle(
                          icon: Icons.schedule,
                          title: 'Highest-pressure time windows',
                        ),
                        const SizedBox(height: 14),
                        _TimeWindows(report: report!),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        const _SectionTitle(
                          icon: Icons.warning_amber_rounded,
                          title: 'Highest-priority findings',
                        ),
                        const SizedBox(height: 12),
                        ...report!.findings.take(8).map(
                              (finding) => _FindingTile(finding: finding),
                            ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

final class _MetricsRow extends StatelessWidget {
  const _MetricsRow({required this.report});
  final SimulationReport report;

  @override
  Widget build(BuildContext context) {
    final credential = report.findings
        .where((finding) => finding.vector == ThreatVector.credentialExposure)
        .fold<double>(
          0,
          (max, finding) =>
              finding.probability > max ? finding.probability : max,
        );
    final human = report.findings
        .where(
          (finding) =>
              finding.vector == ThreatVector.phishing ||
              finding.vector == ThreatVector.socialEngineering,
        )
        .fold<double>(
          0,
          (max, finding) =>
              finding.probability > max ? finding.probability : max,
        );
    final physical = report.findings
        .where((finding) => finding.vector == ThreatVector.physicalIntrusion)
        .fold<double>(
          0,
          (max, finding) =>
              finding.probability > max ? finding.probability : max,
        );
    return LayoutBuilder(
      builder: (context, constraints) {
        final meters = <Widget>[
          RiskMeter(value: report.overallRisk, label: 'Overall'),
          RiskMeter(value: credential, label: 'Keys'),
          RiskMeter(value: human, label: 'Human'),
          RiskMeter(value: physical, label: 'Physical'),
        ];
        if (constraints.maxWidth < 720) {
          return Wrap(
            alignment: WrapAlignment.center,
            spacing: 12,
            runSpacing: 12,
            children: meters,
          );
        }
        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: meters,
        );
      },
    );
  }
}

final class _SurfacePage extends StatelessWidget {
  const _SurfacePage({required this.scenario, required this.report});
  final SimulationScenario scenario;
  final SimulationReport? report;

  @override
  Widget build(BuildContext context) {
    return _PageShell(
      title: 'Attack-surface digital twin',
      subtitle:
          'A non-operational graph of trust relationships, physical locations, identity dependencies, and control coverage.',
      child: ListView(
        padding: EdgeInsets.zero,
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: AttackSurfaceMap(scenario: scenario),
            ),
          ),
          const SizedBox(height: 18),
          _ResponsivePair(
            first: Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const _SectionTitle(icon: Icons.inventory_2, title: 'Assets'),
                    const SizedBox(height: 10),
                    ...scenario.assets.map(
                      (asset) => ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: CircleAvatar(
                          child: Text(asset.name.substring(0, 1)),
                        ),
                        title: Text(asset.name),
                        subtitle: Text('${asset.kind.name} · ${asset.location}'),
                        trailing: Text('${(asset.criticality * 100).round()}%'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            second: Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const _SectionTitle(icon: Icons.security, title: 'Controls'),
                    const SizedBox(height: 10),
                    ...scenario.controls.map(
                      (control) => ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(control.name),
                        subtitle: Text(control.type.name),
                        trailing: Text(
                          '${(control.effectiveness * control.coverage * 100).round()}%',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (report != null) ...<Widget>[
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: _LocationHotspots(report: report!),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

final class _CouncilPage extends StatelessWidget {
  const _CouncilPage({
    required this.adapters,
    required this.council,
    required this.running,
    required this.enabled,
    required this.onRun,
  });

  final List<LlmAdapter> adapters;
  final CouncilReport? council;
  final bool running;
  final bool enabled;
  final VoidCallback onRun;

  @override
  Widget build(BuildContext context) {
    return _PageShell(
      title: 'Multi-model blue-team council',
      subtitle:
          'Compare independent defensive opinions while keeping scenario data redacted and policy constrained.',
      actions: <Widget>[
        FilledButton.icon(
          onPressed: enabled && !running ? onRun : null,
          icon: running
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.forum),
          label: Text(running ? 'Council deliberating…' : 'Run model council'),
        ),
      ],
      child: ListView(
        padding: EdgeInsets.zero,
        children: <Widget>[
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: adapters
                .map((adapter) => _ModelCard(adapter: adapter))
                .toList(),
          ),
          const SizedBox(height: 18),
          if (council == null)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Offline analysis is always available. Cloud providers activate only when their API keys are supplied with --dart-define. Local Gemma activates only when explicitly enabled.',
                ),
              ),
            )
          else ...<Widget>[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(22),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const _SectionTitle(icon: Icons.how_to_vote, title: 'Consensus'),
                    const SizedBox(height: 14),
                    Text(
                      council!.consensusSummary,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 14),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: council!.consensusVectors
                          .map((vector) => Chip(label: Text(vector.name)))
                          .toList(),
                    ),
                    const SizedBox(height: 12),
                    Text('Secrets redacted before model calls: ${council!.redactionCount}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            ...council!.opinions.map((opinion) => _OpinionCard(opinion: opinion)),
          ],
        ],
      ),
    );
  }
}

final class _SafetyPage extends StatelessWidget {
  const _SafetyPage({required this.scenario});
  final SimulationScenario scenario;

  @override
  Widget build(BuildContext context) {
    final jsonText = const JsonEncoder.withIndent('  ').convert(scenario.toJson());
    return _PageShell(
      title: 'Authorization and safety boundary',
      subtitle:
          'CyberForge predicts defensive risk. It does not scan live targets, generate attack payloads, steal credentials, or instruct physical intrusion.',
      child: ListView(
        padding: EdgeInsets.zero,
        children: <Widget>[
          const _BoundaryCard(
            icon: Icons.verified_user,
            title: 'Allowed',
            text:
                'Synthetic digital twins, authorized control validation, threat modeling, tabletop exercises, safe telemetry analysis, security training, and remediation prioritization.',
          ),
          const SizedBox(height: 12),
          const _BoundaryCard(
            icon: Icons.block,
            title: 'Blocked',
            text:
                'Exploit payloads, credential theft, real phishing content, malware deployment, evasion instructions, live-target probing, and physical break-in procedures.',
          ),
          const SizedBox(height: 18),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const _SectionTitle(icon: Icons.gavel, title: 'Current authorization'),
                  const SizedBox(height: 12),
                  Text(scenario.authorizationStatement),
                  const SizedBox(height: 10),
                  Text('Synthetic data: ${scenario.synthetic ? 'yes' : 'no'}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const _SectionTitle(icon: Icons.data_object, title: 'Scenario packet'),
                  const SizedBox(height: 12),
                  SelectableText(
                    jsonText,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: CyberForgeColors.muted,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

final class _PageShell extends StatelessWidget {
  const _PageShell({
    required this.title,
    required this.subtitle,
    required this.child,
    this.actions = const <Widget>[],
  });

  final String title;
  final String subtitle;
  final Widget child;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 18,
            runSpacing: 14,
            children: <Widget>[
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 760),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(title, style: Theme.of(context).textTheme.headlineLarge),
                    const SizedBox(height: 7),
                    Text(subtitle, style: Theme.of(context).textTheme.bodyLarge),
                  ],
                ),
              ),
              ...actions,
            ],
          ),
          const SizedBox(height: 24),
          Expanded(child: child),
        ],
      ),
    );
  }
}

final class _ResponsivePair extends StatelessWidget {
  const _ResponsivePair({required this.first, required this.second});
  final Widget first;
  final Widget second;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 760) {
          return Column(
            children: <Widget>[
              first,
              const SizedBox(height: 14),
              second,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(child: first),
            const SizedBox(width: 14),
            Expanded(child: second),
          ],
        );
      },
    );
  }
}

final class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title});
  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, color: CyberForgeColors.cyan),
        const SizedBox(width: 9),
        Text(title, style: Theme.of(context).textTheme.titleLarge),
      ],
    );
  }
}

final class _FindingTile extends StatelessWidget {
  const _FindingTile({required this.finding});
  final RiskFinding finding;

  @override
  Widget build(BuildContext context) {
    final color = switch (finding.severity) {
      Severity.critical || Severity.high => CyberForgeColors.red,
      Severity.medium => CyberForgeColors.amber,
      _ => CyberForgeColors.green,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: CyberForgeColors.surfaceRaised,
          borderRadius: BorderRadius.circular(14),
        ),
        child: ListTile(
          leading: Container(
            width: 10,
            height: 42,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          title: Text(finding.title),
          subtitle: Text('${finding.location} · ${finding.likelyWindow}'),
          trailing: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Text('${finding.riskScore.toStringAsFixed(1)} risk'),
              Text('${(finding.confidence * 100).round()}% confidence'),
            ],
          ),
        ),
      ),
    );
  }
}

final class _LocationHotspots extends StatelessWidget {
  const _LocationHotspots({required this.report});
  final SimulationReport report;

  @override
  Widget build(BuildContext context) {
    final entries = report.locationRisk.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text('Likely hotspots', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        ...entries.take(6).map(
          (entry) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              children: <Widget>[
                Expanded(flex: 3, child: Text(entry.key)),
                Expanded(
                  flex: 4,
                  child: LinearProgressIndicator(
                    value: entry.value,
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  width: 42,
                  child: Text('${(entry.value * 100).round()}%'),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

final class _TimeWindows extends StatelessWidget {
  const _TimeWindows({required this.report});

  final SimulationReport report;

  @override
  Widget build(BuildContext context) {
    final entries = report.timelineRisk.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: entries.take(8).map((entry) {
        final nextHour = (entry.key + 1) % 24;
        final label =
            "${entry.key.toString().padLeft(2, '0')}:00–${nextHour.toString().padLeft(2, '0')}:00";
        return SizedBox(
          width: 190,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: CyberForgeColors.surfaceRaised,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: CyberForgeColors.grid),
            ),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(label, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 10),
                  LinearProgressIndicator(
                    value: entry.value,
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  const SizedBox(height: 7),
                  Text('${(entry.value * 100).round()}% relative pressure'),
                ],
              ),
            ),
          ),
        );
      }).toList(growable: false),
    );
  }
}

final class _TelemetryLine extends StatelessWidget {
  const _TelemetryLine({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: <Widget>[
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(color: CyberForgeColors.cyan)),
        ],
      ),
    );
  }
}

final class _ModelCard extends StatelessWidget {
  const _ModelCard({required this.adapter});
  final LlmAdapter adapter;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 230,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(
                    adapter.configured
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                    color: adapter.configured
                        ? CyberForgeColors.green
                        : CyberForgeColors.muted,
                  ),
                  const Spacer(),
                  Text(adapter.provider.name),
                ],
              ),
              const SizedBox(height: 12),
              Text(adapter.model, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(adapter.configured ? 'Ready' : 'Not configured'),
            ],
          ),
        ),
      ),
    );
  }
}

final class _OpinionCard extends StatelessWidget {
  const _OpinionCard({required this.opinion});
  final ModelOpinion opinion;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(
                    opinion.succeeded ? Icons.check_circle : Icons.error_outline,
                    color: opinion.succeeded
                        ? CyberForgeColors.green
                        : CyberForgeColors.red,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      opinion.model,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  Text('${opinion.latencyMilliseconds} ms'),
                ],
              ),
              const SizedBox(height: 12),
              Text(opinion.error ?? opinion.summary),
              if (opinion.recommendedControls.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                ...opinion.recommendedControls.take(5).map(
                      (control) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('• $control'),
                      ),
                    ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

final class _BoundaryCard extends StatelessWidget {
  const _BoundaryCard({
    required this.icon,
    required this.title,
    required this.text,
  });

  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(icon, color: CyberForgeColors.cyan, size: 30),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(title, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text(text),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
