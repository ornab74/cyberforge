import 'package:flutter/material.dart';

import 'backend/secure_config_store.dart';
import 'theme/cyberforge_theme.dart';
import 'ui/cyberforge_workspace.dart';
import 'ui/startup_setup_flow.dart';

final class CyberForgeApp extends StatefulWidget {
  const CyberForgeApp({super.key});

  @override
  State<CyberForgeApp> createState() => _CyberForgeAppState();
}

final class _CyberForgeAppState extends State<CyberForgeApp> {
  final _config = SecureConfigStore();
  late Future<bool> _setupComplete = _config.isSetupComplete();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CyberForge 4',
      debugShowCheckedModeBanner: false,
      theme: CyberForgeTheme.dark(),
      home: FutureBuilder<bool>(
        future: _setupComplete,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          if (snapshot.data == true) {
            return const CyberForgeWorkspace();
          }
          return StartupSetupFlow(
            onComplete: () => setState(
              () => _setupComplete = Future<bool>.value(true),
            ),
          );
        },
      ),
    );
  }
}
