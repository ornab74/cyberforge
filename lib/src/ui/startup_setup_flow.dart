import 'package:flutter/material.dart';

import '../backend/secure_config_store.dart';

final class StartupSetupFlow extends StatefulWidget {
  const StartupSetupFlow({required this.onComplete, super.key});

  final VoidCallback onComplete;

  @override
  State<StartupSetupFlow> createState() => _StartupSetupFlowState();
}

final class _StartupSetupFlowState extends State<StartupSetupFlow> {
  final _store = SecureConfigStore();
  final _recovery = TextEditingController();
  final _meta = TextEditingController();
  final _openAi = TextEditingController();
  final _xai = TextEditingController();
  final _gemini = TextEditingController();
  final _digitalOcean = TextEditingController();
  int _step = 0;
  bool _localModels = true;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    for (final controller in [
      _recovery,
      _meta,
      _openAi,
      _xai,
      _gemini,
      _digitalOcean,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [_welcome(), _vault(), _providers(), _local(), _review()];
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920),
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(children: [
                    const Icon(Icons.security_rounded, size: 34),
                    const SizedBox(width: 12),
                    Text('CyberForge secure startup',
                        style: Theme.of(context).textTheme.headlineSmall),
                    const Spacer(),
                    Text('${_step + 1} / ${pages.length}'),
                  ]),
                  const SizedBox(height: 18),
                  LinearProgressIndicator(value: (_step + 1) / pages.length),
                  const SizedBox(height: 28),
                  Expanded(child: SingleChildScrollView(child: pages[_step])),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: Colors.redAccent)),
                  ],
                  const SizedBox(height: 18),
                  Row(children: [
                    if (_step > 0)
                      TextButton(
                        onPressed: _busy ? null : () => setState(() => _step--),
                        child: const Text('Back'),
                      ),
                    const Spacer(),
                    FilledButton.icon(
                      onPressed: _busy ? null : _next,
                      icon: _busy
                          ? const SizedBox.square(
                              dimension: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Icon(_step == pages.length - 1
                              ? Icons.rocket_launch_rounded
                              : Icons.arrow_forward_rounded),
                      label: Text(_step == pages.length - 1
                          ? 'Enter command center'
                          : 'Continue'),
                    ),
                  ]),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _welcome() => const _SetupSection(
        title: 'Build a private control plane first',
        body:
            'CyberForge now keeps orchestration in Dart. This guided setup stores secrets in the operating-system credential vault, configures optional cloud critics, and prepares an isolated local inference worker. No key is written to .env or passed on a command line.',
        icon: Icons.hub_rounded,
      );

  Widget _vault() => _SetupSection(
        title: 'Create a recovery key',
        body:
            'Use a long, unique value. It protects future encrypted exports and recovery envelopes. CyberForge never uploads it.',
        icon: Icons.key_rounded,
        child: TextField(
          controller: _recovery,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Vault recovery key',
            helperText: 'Minimum 20 characters',
            border: OutlineInputBorder(),
          ),
        ),
      );

  Widget _providers() => _SetupSection(
        title: 'Connect optional model providers',
        body:
            'All providers are optional. Meta Muse Spark 1.1 is added as a first-class council member. Remote models remain disabled per scan until explicitly enabled.',
        icon: Icons.auto_awesome_rounded,
        child: Column(children: [
          _secret(_meta, 'Meta Model API key', 'Muse Spark 1.1'),
          _secret(_openAi, 'OpenAI API key', 'GPT critic'),
          _secret(_xai, 'xAI API key', 'Grok critic'),
          _secret(_gemini, 'Google Gemini API key', 'Gemini critic'),
          _secret(_digitalOcean, 'DigitalOcean model key', 'Gradient AI critic'),
        ]),
      );

  Widget _local() => _SetupSection(
        title: 'Local model runtime',
        body:
            'The Dart backend can create a project-local Python environment and install llama-cpp-python as a subordinate inference worker. Python receives only prompts and model paths—never cloud keys or recovery material.',
        icon: Icons.memory_rounded,
        child: SwitchListTile.adaptive(
          value: _localModels,
          onChanged: (value) => setState(() => _localModels = value),
          title: const Text('Prepare local llama.cpp worker after setup'),
          subtitle: const Text(
            'Installation remains explicit and can be disabled by policy.',
          ),
        ),
      );

  Widget _review() => _SetupSection(
        title: 'Ready to forge',
        body:
            'Your startup choices will be saved to secure storage. Keys are never displayed again. Provider connectivity and local runtime installation can be tested from Vault & Models.',
        icon: Icons.verified_user_rounded,
        child: Wrap(spacing: 10, runSpacing: 10, children: [
          Chip(label: Text(_meta.text.isEmpty ? 'Muse not configured' : 'Muse ready')),
          Chip(label: Text(_localModels ? 'Local runtime enabled' : 'Cloud/offline only')),
          const Chip(label: Text('Remote scans opt-in')),
        ]),
      );

  Widget _secret(TextEditingController controller, String label, String hint) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextField(
          controller: controller,
          obscureText: true,
          decoration: InputDecoration(
            labelText: label,
            helperText: hint,
            border: const OutlineInputBorder(),
          ),
        ),
      );

  Future<void> _next() async {
    setState(() => _error = null);
    if (_step == 1 && _recovery.text.trim().length < 20) {
      setState(() => _error = 'Use a recovery key with at least 20 characters.');
      return;
    }
    if (_step < 4) {
      setState(() => _step++);
      return;
    }
    setState(() => _busy = true);
    try {
      await _store.writeSecret('vault_recovery_key', _recovery.text);
      await _store.writeSecret('meta_model_api_key', _meta.text);
      await _store.writeSecret('openai_api_key', _openAi.text);
      await _store.writeSecret('xai_api_key', _xai.text);
      await _store.writeSecret('gemini_api_key', _gemini.text);
      await _store.writeSecret('digitalocean_api_key', _digitalOcean.text);
      await _store.saveMetadata(<String, Object?>{
        'localModelsEnabled': _localModels,
        'remoteModelsDefault': false,
        'backend': 'dart',
      });
      await _store.markSetupComplete();
      widget.onComplete();
    } catch (error) {
      setState(() => _error = 'Secure setup failed: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

final class _SetupSection extends StatelessWidget {
  const _SetupSection({
    required this.title,
    required this.body,
    required this.icon,
    this.child,
  });

  final String title;
  final String body;
  final IconData icon;
  final Widget? child;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(26),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 44),
              const SizedBox(height: 18),
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 12),
              Text(body, style: Theme.of(context).textTheme.bodyLarge),
              if (child != null) ...[const SizedBox(height: 24), child!],
            ],
          ),
        ),
      );
}
