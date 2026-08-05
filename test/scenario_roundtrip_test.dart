import 'dart:convert';

import 'package:cyberforge/src/domain/models.dart';
import 'package:cyberforge/src/repository/scenario_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('scenario JSON round trip preserves graph and controls', () {
    final source = const ScenarioRepository().demo();
    final decoded = SimulationScenario.fromJson(
      Map<String, Object?>.from(jsonDecode(source.prettyJson()) as Map),
    );

    expect(decoded.id, source.id);
    expect(decoded.assets.length, source.assets.length);
    expect(decoded.controls.length, source.controls.length);
    expect(decoded.edges.length, source.edges.length);
    expect(decoded.seed, source.seed);
  });
}
