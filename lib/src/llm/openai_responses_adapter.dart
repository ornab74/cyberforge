import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';
import 'http_helpers.dart';
import 'llm_adapter.dart';

final class OpenAiResponsesAdapter implements LlmAdapter {
  OpenAiResponsesAdapter({
    String? apiKey,
    this.model = const String.fromEnvironment(
      'OPENAI_MODEL',
      defaultValue: 'gpt-5.6',
    ),
    http.Client? client,
  })  : apiKey = apiKey ?? const String.fromEnvironment('OPENAI_API_KEY'),
        _client = client ?? http.Client();

  final String apiKey;
  @override
  final String model;
  final http.Client _client;

  @override
  ModelProvider get provider => ModelProvider.openAi;

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
            Uri.parse('https://api.openai.com/v1/responses'),
            headers: <String, String>{
              'Authorization': 'Bearer $apiKey',
              'Content-Type': 'application/json',
            },
            body: jsonEncode(<String, Object?>{
              'model': model,
              'input': policyPrompt,
              'reasoning': <String, Object?>{'effort': 'medium'},
            }),
          )
          .timeout(const Duration(seconds: 75));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('OpenAI HTTP ${response.statusCode}: ${response.body}');
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
