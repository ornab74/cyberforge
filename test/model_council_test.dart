import 'package:cyberforge/src/engine/simulation_engine.dart';
import 'package:cyberforge/src/llm/model_council.dart';
import 'package:cyberforge/src/llm/offline_policy_adapter.dart';
import 'package:cyberforge/src/repository/scenario_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('offline council produces a defensive consensus packet', () async {
    final scenario = const ScenarioRepository().demo();
    final simulation = await const SimulationEngine().run(
      scenario,
      iterations: 500,
    );
    final council = await const ModelCouncil(
      adapters: <OfflinePolicyAdapter>[OfflinePolicyAdapter()],
    ).deliberate(scenario: scenario, report: simulation);

    expect(council.opinions, hasLength(1));
    expect(council.opinions.single.succeeded, isTrue);
    expect(council.consensusSummary, contains('Council consensus'));
    expect(council.consensusControls, isNotEmpty);
  });
}
