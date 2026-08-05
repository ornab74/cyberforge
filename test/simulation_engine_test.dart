import 'package:cyberforge/src/engine/simulation_engine.dart';
import 'package:cyberforge/src/repository/scenario_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('simulation returns bounded, defense-oriented findings', () async {
    final scenario = const ScenarioRepository().demo();
    final report = await const SimulationEngine().run(
      scenario,
      iterations: 800,
    );

    expect(report.overallRisk, inInclusiveRange(0.0, 1.0));
    expect(report.findings, isNotEmpty);
    expect(report.timelineRisk.keys, containsAll(<int>[0, 12, 23]));
    expect(report.telemetry.simulatedQubitRegister, 3923929);
    expect(report.telemetry.iterations, 800);
    expect(
      report.telemetry.toJson()['disclaimer'],
      contains('no physical quantum'),
    );
    for (final finding in report.findings) {
      expect(finding.probability, inInclusiveRange(0.0, 1.0));
      expect(finding.impact, inInclusiveRange(0.0, 1.0));
      expect(finding.recommendations, isNotEmpty);
    }
  });
}
