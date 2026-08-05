import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';
import 'http_helpers.dart';
import 'llm_adapter.dart';

final class XaiResponsesAdapter implements LlmAdapter {
  XaiResponsesAdapter({
    String? apiKey,
    this.model = const String.fromEnvironment(
      'XAI_MODEL',
      defaultValue: 'grok-4.5',
    ),
    http.Client? client,
  })  : apiKey = apiKey ?? const String.fromEnvironment('XAI_API_KEY'),
        _client = client ?? http.Client();

  final String apiKey;
  @override
  final String model;
  final http.Client _client;

  @override
  ModelProvider get provider => ModelProvider.xAi;

  @override
  bool get configured => apiKey.trim().isNotEmpty;

  @override
  Future<ModelOpinion> analyze({
    required SimulationScenario scenario,
    required SimulationReport report,
    required String policyPrompt,
  }) async {
    final watch = Stopwatch()..start();
    try {
      final response = await _client
          .post(
            Uri.parse('https://api.x.ai/v1/responses'),
            headers: <String, String>{
              'Authorization': 'Bearer $apiKey',
              'Content-Type': 'application/json',
            },
            body: jsonEncode(<String, Object?>{
              'model': model,
              'input': policyPrompt,
              'reasoning_effort': 'medium',
            }),
          )
          .timeout(const Duration(seconds: 75));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('xAI HTTP ${response.statusCode}: ${response.body}');
      }
      final decoded = jsonDecode(response.body) as Map<String, Object?>;
      return parseOpinion(
        provider: provider,
        model: model,
        text: extractResponsesApiText(decoded),
        latencyMilliseconds: watch.elapsedMilliseconds,
      );
    } catch (error) {
      return ModelOpinion.failure(
        provider: provider,
        model: model,
        error: error,
        latencyMilliseconds: watch.elapsedMilliseconds,
      );
    }
  }
}
