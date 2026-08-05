import '../domain/models.dart';
import 'llm_adapter.dart';

final class OfflinePolicyAdapter implements LlmAdapter {
  const OfflinePolicyAdapter();

  @override
  ModelProvider get provider => ModelProvider.offline;

  @override
  String get model => 'cyberforge-policy-ensemble-v1';

  @override
  bool get configured => true;

  @override
  Future<ModelOpinion> analyze({
    required SimulationScenario scenario,
    required SimulationReport report,
    required String policyPrompt,
  }) async {
    final top = report.findings.take(5).toList(growable: false);
    return ModelOpinion(
      provider: provider,
      model: model,
      summary: report.defensiveSummary,
      priorityVectors:
          top.map((finding) => finding.vector).toSet().toList(growable: false),
      recommendedControls: top
          .expand((finding) => finding.recommendations)
          .toSet()
          .take(8)
          .toList(growable: false),
      uncertainty: 1 - report.telemetry.coherence,
      assumptions: const <String>[
        'Uses CyberForge deterministic and Monte Carlo risk signals only.',
        'Does not inspect live networks or execute offensive actions.',
      ],
      latencyMilliseconds: 1,
    );
  }
}
