import 'package:flutter/material.dart';

import '../backend/secure_config_store.dart';
import '../theme/cyberforge_theme.dart';

/// Super-advanced first-boot / first-run guide for AEGIS-816 CyberForge.
final class AdvancedBootGuide extends StatefulWidget {
  const AdvancedBootGuide({
    required this.onFinished,
    this.forceShow = false,
    super.key,
  });

  final VoidCallback onFinished;
  final bool forceShow;

  @override
  State<AdvancedBootGuide> createState() => _AdvancedBootGuideState();
}

final class _AdvancedBootGuideState extends State<AdvancedBootGuide> {
  final _store = SecureConfigStore();
  final _pageController = PageController();
  var _page = 0;
  var _busy = false;

  static const _pages = <_GuidePage>[
    _GuidePage(
      eyebrow: 'AEGIS-816 // BOOT SEQUENCE',
      title: 'Welcome to CyberForge Command Center',
      body:
          'You are entering a local-first blue-team digital twin. Dyson Sphere Gamma language, 81,611,511 qubits, and FTL SIMCOM relays are high-density interface metaphors on conventional hardware. The real fabric is your authorized scenario graph, Monte Carlo engine, encrypted vault, and model council.',
      bullets: <String>[
        'Sidecar binds to 127.0.0.1:8788 only',
        'Vault unlock runs automatically every boot (device key, then password)',
        'Remote council models stay opt-in per scan',
        'SimForensics is a lattice calibre — not LEA forensics',
      ],
      icon: Icons.hub_rounded,
    ),
    _GuidePage(
      eyebrow: 'VAULT // AES-256-GCM + ARGON2ID',
      title: 'Encrypted control plane',
      body:
          'Provider keys and model-at-rest keys live in the local vault. On every launch CyberForge attempts device-key unlock, then the vault password from secure config. Session tokens stay short-lived and loopback-only.',
      bullets: <String>[
        'Create vault once under Vault & Models',
        'Store OpenAI / xAI / DigitalOcean / Gemini keys in the vault',
        'Load Llama + Gemma profiles after unlock',
        'Rotate data keys when staff or laptops change',
      ],
      icon: Icons.lock_rounded,
    ),
    _GuidePage(
      eyebrow: 'LATTICE // INDIVIDUAL MICRO-SCANNER',
      title: 'Any individual, not just VPN edges',
      body:
          'Llama 3 small scans ranked individuals (identity, human, endpoint, server, network/vpn, api, cloud, facility, route, vendor, data, collective). Host entropy uses psutil + PennyLane-style scoring; optional GPT-5.6 rewrites the Llama prompt per context; PUNKD + chunked generation stabilizes small-model JSON.',
      bullets: <String>[
        'Load llama3-small-q3 for micro-passes',
        'Load gemma4-e2b-litert-4bit for private synthesis',
        'GPT-5.6 composer activates when OpenAI is vaulted',
        'Lattice telemetry lands on each micro-scan result',
      ],
      icon: Icons.memory_rounded,
    ),
    _GuidePage(
      eyebrow: 'SIMCOM // DATAPULL + AMCCS',
      title: 'Terminal-grade twin dialogue',
      body:
          'SIMCOM is the cinematic command surface. ./datapull runs Adaptive Multimodel Consensus Chunking (AMCCS) with SimForensics calibre for entry classes, timelines, scale ranges, and simulated ISO-2 projections — always labeled predictive until real IR packages arrive.',
      bullets: <String>[
        'bootcom · status · scan · timeline · impact',
        './datapull <topic> --mode single|multi',
        'simcom entry_vector --mode predictive --scope <id>',
        'origin for forensic boundary; origin --mode predictive for lattice ISO-2',
      ],
      icon: Icons.terminal_rounded,
    ),
    _GuidePage(
      eyebrow: 'MISSION // AUTHORIZED TWINS ONLY',
      title: 'How to run your first super scan',
      body:
          'Authorize the scenario, set worlds/seed, optionally enable remote council, then run the super scanner. Review risk arc, surface matrix, hotspots, trust paths, council disagreement, and SIMCOM export. Re-run with higher worlds for tighter Monte Carlo bands.',
      bullets: <String>[
        '1. Confirm vault UNLOCKED in the header',
        '2. Load local models you intend to use',
        '3. Review surfaces in the scenario twin',
        '4. Run scan → inspect council → datapull topics of interest',
        '5. Export structured report for your IR workflow',
      ],
      icon: Icons.rocket_launch_rounded,
    ),
  ];

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _finish() async {
    setState(() => _busy = true);
    try {
      await _store.markAdvancedGuideComplete();
      widget.onFinished();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: CyberForgeColors.background.withValues(alpha: 0.96),
      child: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920, maxHeight: 720),
            child: Card(
              color: CyberForgeColors.surface,
              elevation: 12,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
                side: BorderSide(color: CyberForgeColors.grid.withValues(alpha: 0.8)),
              ),
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.auto_awesome, color: CyberForgeColors.cyan),
                        const SizedBox(width: 10),
                        Text(
                          'CYBERFORGE ADVANCED BOOT GUIDE',
                          style: theme.textTheme.titleMedium?.copyWith(
                            color: CyberForgeColors.cyan,
                            letterSpacing: 1.2,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${_page + 1} / ${_pages.length}',
                          style: theme.textTheme.labelLarge?.copyWith(
                            color: CyberForgeColors.muted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    LinearProgressIndicator(
                      value: (_page + 1) / _pages.length,
                      color: CyberForgeColors.cyan,
                      backgroundColor: CyberForgeColors.grid,
                    ),
                    const SizedBox(height: 18),
                    Expanded(
                      child: PageView.builder(
                        controller: _pageController,
                        itemCount: _pages.length,
                        onPageChanged: (value) => setState(() => _page = value),
                        itemBuilder: (context, index) {
                          final page = _pages[index];
                          return SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(page.icon, size: 48, color: CyberForgeColors.violet),
                                const SizedBox(height: 16),
                                Text(
                                  page.eyebrow,
                                  style: theme.textTheme.labelLarge?.copyWith(
                                    color: CyberForgeColors.amber,
                                    letterSpacing: 1.1,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  page.title,
                                  style: theme.textTheme.headlineSmall?.copyWith(
                                    color: CyberForgeColors.text,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 14),
                                Text(
                                  page.body,
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    color: CyberForgeColors.muted,
                                    height: 1.45,
                                  ),
                                ),
                                const SizedBox(height: 18),
                                ...page.bullets.map(
                                  (item) => Padding(
                                    padding: const EdgeInsets.only(bottom: 8),
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const Icon(
                                          Icons.chevron_right,
                                          size: 18,
                                          color: CyberForgeColors.green,
                                        ),
                                        const SizedBox(width: 6),
                                        Expanded(
                                          child: Text(
                                            item,
                                            style: theme.textTheme.bodyMedium?.copyWith(
                                              color: CyberForgeColors.text,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        TextButton(
                          onPressed: _busy
                              ? null
                              : () async {
                                  await _store.markAdvancedGuideComplete();
                                  widget.onFinished();
                                },
                          child: const Text('Skip guide'),
                        ),
                        const Spacer(),
                        if (_page > 0)
                          TextButton(
                            onPressed: _busy
                                ? null
                                : () => _pageController.previousPage(
                                      duration: const Duration(milliseconds: 280),
                                      curve: Curves.easeOut,
                                    ),
                            child: const Text('Back'),
                          ),
                        const SizedBox(width: 8),
                        FilledButton.icon(
                          onPressed: _busy
                              ? null
                              : () {
                                  if (_page >= _pages.length - 1) {
                                    _finish();
                                    return;
                                  }
                                  _pageController.nextPage(
                                    duration: const Duration(milliseconds: 280),
                                    curve: Curves.easeOut,
                                  );
                                },
                          icon: Icon(
                            _page >= _pages.length - 1
                                ? Icons.rocket_launch_rounded
                                : Icons.arrow_forward_rounded,
                          ),
                          label: Text(
                            _page >= _pages.length - 1
                                ? 'Enter command center'
                                : 'Continue',
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

final class _GuidePage {
  const _GuidePage({
    required this.eyebrow,
    required this.title,
    required this.body,
    required this.bullets,
    required this.icon,
  });

  final String eyebrow;
  final String title;
  final String body;
  final List<String> bullets;
  final IconData icon;
}
