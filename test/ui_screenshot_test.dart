import 'package:cyberforge/src/theme/cyberforge_theme.dart';
import 'package:cyberforge/src/ui/startup_setup_flow.dart';
import 'package:cyberforge/src/v3/cyberforge_command_center.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('startup setup golden screenshot', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: CyberForgeTheme.dark(),
        home: StartupSetupFlow(onComplete: () {}),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('../screenshots/cyberforge_startup_golden.png'),
    );
  });

  testWidgets('command center golden screenshot', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1440, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: CyberForgeTheme.dark(),
        home: const CyberForgeCommandCenter(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('../screenshots/cyberforge_command_center_golden.png'),
    );
  });
}
