import 'package:flutter/material.dart';

import 'theme/cyberforge_theme.dart';
import 'v3/cyberforge_command_center.dart';

final class CyberForgeApp extends StatelessWidget {
  const CyberForgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CyberForge 3',
      debugShowCheckedModeBanner: false,
      theme: CyberForgeTheme.dark(),
      home: const CyberForgeCommandCenter(),
    );
  }
}
