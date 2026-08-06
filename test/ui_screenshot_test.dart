import 'dart:io';

import 'package:cyberforge/src/theme/cyberforge_theme.dart';
import 'package:cyberforge/src/ui/startup_setup_flow.dart';
import 'package:cyberforge/src/v3/cyberforge_command_center.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

final bool _runGoldens =
    Platform.environment['CYBERFORGE_RUN_GOLDENS']?.toLowerCase() == 'true';

void main() {
  testWidgets('startup setup surface renders', (tester) async {
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

    expect(find.byType(StartupSetupFlow), findsOneWidget);
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(tester.takeException(), isNull);

    if (_runGoldens) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('../screenshots/cyberforge_startup_golden.png'),
      );
    }
  });

  testWidgets('command center surface renders', (tester) async {
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

    // The command center intentionally retries the loopback sidecar during
    // startup. Advance fake time through all bounded retry delays so the test
    // does not finish with an application timer still pending.
    for (var attempt = 0; attempt < 14; attempt++) {
      await tester.pump(const Duration(milliseconds: 300));
    }

    expect(find.byType(CyberForgeCommandCenter), findsOneWidget);
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(tester.takeException(), isNull);

    if (_runGoldens) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('../screenshots/cyberforge_command_center_golden.png'),
      );
    }

    // Explicitly dispose the command center and complete any final microtasks.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
