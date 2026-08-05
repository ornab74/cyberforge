import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';
import 'http_helpers.dart';
import 'llm_adapter.dart';

final class GeminiAdapter implements LlmAdapter {
  GeminiAdapter({
    String? apiKey,
    this.model = const String.fromEnvironment(
      'GEMINI_MODEL',
      defaultValue: 'gemini-3.6-flash',
    ),
    http.Client? client,
  })  : apiKey = apiKey ?? const String.fromEnvironment('GEMINI_API_KEY'),
        _client = client ?? http.Client();

  final String apiKey;
  @override
  final String model;
  final http.Client _client;

  @override
  ModelProvider get provider => ModelProvider.gemini;

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
      final uri = Uri.parse(
        'https://generativelanguage.googleapis.com/v1beta/models/$model:generateContent',
      );
      final response = await _client
          .post(
            uri,
            headers: <String, String>{
              'Content-Type': 'application/json',
              'x-goog-api-key': apiKey,
            },
            body: jsonEncode(<String, Object?>{
              'contents': <Object?>[
                <String, Object?>{
                  'role': 'user',
                  'parts': <Object?>[
                    <String, Object?>{'text': policyPrompt},
                  ],
                },
              ],
              'generationConfig': <String, Object?>{
                'responseMimeType': 'application/json',
                'temperature': 0.2,
              },
            }),
          )
          .timeout(const Duration(seconds: 75));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('Gemini HTTP ${response.statusCode}: ${response.body}');
      }
      final decoded = jsonDecode(response.body) as Map<String, Object?>;
      return parseOpinion(
        provider: provider,
        model: model,
        text: extractGeminiText(decoded),
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
