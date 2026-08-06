import 'package:cyberforge/src/theme/cyberforge_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('CyberForge theme renders a stable smoke surface', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: CyberForgeTheme.dark(),
        home: const Scaffold(
          body: Center(child: Text('CyberForge CI ready')),
        ),
      ),
    );

    expect(find.text('CyberForge CI ready'), findsOneWidget);
    expect(find.byType(Scaffold), findsOneWidget);
  });
}
