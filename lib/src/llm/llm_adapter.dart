import 'dart:convert';

import '../domain/models.dart';

enum ModelProvider { openAi, xAi, gemini, gemmaLocal, offline }

final class ModelOpinion {
  const ModelOpinion({
    required this.provider,
    required this.model,
    required this.summary,
    required this.priorityVectors,
    required this.recommendedControls,
    required this.uncertainty,
    required this.assumptions,
    this.rawText = '',
    this.latencyMilliseconds = 0,
    this.error,
  });

  final ModelProvider provider;
  final String model;
  final String summary;
  final List<ThreatVector> priorityVectors;
  final List<String> recommendedControls;
  final double uncertainty;
  final List<String> assumptions;
  final String rawText;
  final int latencyMilliseconds;
  final String? error;

  bool get succeeded => error == null;

  Map<String, Object?> toJson() => <String, Object?>{
        'provider': provider.name,
        'model': model,
        'summary': summary,
        'priorityVectors': priorityVectors.map((e) => e.name).toList(),
        'recommendedControls': recommendedControls,
        'uncertainty': uncertainty,
        'assumptions': assumptions,
        'latencyMilliseconds': latencyMilliseconds,
        if (error != null) 'error': error,
      };

  factory ModelOpinion.failure({
    required ModelProvider provider,
    required String model,
    required Object error,
    int latencyMilliseconds = 0,
  }) =>
      ModelOpinion(
        provider: provider,
        model: model,
        summary: 'Model did not return an opinion.',
        priorityVectors: const <ThreatVector>[],
        recommendedControls: const <String>[],
        uncertainty: 1,
        assumptions: const <String>[],
        latencyMilliseconds: latencyMilliseconds,
        error: error.toString(),
      );
}

abstract interface class LlmAdapter {
  ModelProvider get provider;
  String get model;
  bool get configured;

  Future<ModelOpinion> analyze({
    required SimulationScenario scenario,
    required SimulationReport report,
    required String policyPrompt,
  });
}

ModelOpinion parseOpinion({
  required ModelProvider provider,
  required String model,
  required String text,
  required int latencyMilliseconds,
}) {
  final normalized = _extractJsonObject(text);
  try {
    final decoded = jsonDecode(normalized) as Map<String, Object?>;
    final vectors = (decoded['priorityVectors'] as List? ?? const <Object?>[])
        .map((item) => item.toString())
        .map((name) => ThreatVector.values.where((e) => e.name == name).firstOrNull)
        .whereType<ThreatVector>()
        .toList(growable: false);
    return ModelOpinion(
      provider: provider,
      model: model,
      summary: decoded['summary']?.toString() ?? text,
      priorityVectors: vectors,
      recommendedControls: List<String>.from(
        decoded['recommendedControls'] as List? ?? const <String>[],
      ),
      uncertainty: ((decoded['uncertainty'] as num?)?.toDouble() ?? 0.5)
          .clamp(0.0, 1.0)
          .toDouble(),
      assumptions: List<String>.from(
        decoded['assumptions'] as List? ?? const <String>[],
      ),
      rawText: text,
      latencyMilliseconds: latencyMilliseconds,
    );
  } catch (_) {
    return ModelOpinion(
      provider: provider,
      model: model,
      summary: text.trim().isEmpty ? 'No model text returned.' : text.trim(),
      priorityVectors: const <ThreatVector>[],
      recommendedControls: const <String>[],
      uncertainty: 0.75,
      assumptions: const <String>['Provider response was not valid JSON.'],
      rawText: text,
      latencyMilliseconds: latencyMilliseconds,
    );
  }
}

String _extractJsonObject(String text) {
  final first = text.indexOf('{');
  final last = text.lastIndexOf('}');
  if (first >= 0 && last > first) return text.substring(first, last + 1);
  return text;
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
