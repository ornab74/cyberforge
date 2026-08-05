import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';
import 'http_helpers.dart';
import 'llm_adapter.dart';

final class GemmaLocalAdapter implements LlmAdapter {
  GemmaLocalAdapter({
    this.endpoint = const String.fromEnvironment(
      'GEMMA_LOCAL_URL',
      defaultValue: 'http://127.0.0.1:8080/v1/chat/completions',
    ),
    this.model = const String.fromEnvironment(
      'GEMMA_LOCAL_MODEL',
      defaultValue: 'gemma-4-e2b-it',
    ),
    bool? enabled,
    http.Client? client,
  })  : enabled = enabled ??
            const bool.fromEnvironment(
              'ENABLE_GEMMA_LOCAL',
              defaultValue: false,
            ),
        _client = client ?? http.Client();

  final String endpoint;
  final bool enabled;
  @override
  final String model;
  final http.Client _client;

  @override
  ModelProvider get provider => ModelProvider.gemmaLocal;

  @override
  bool get configured => enabled && endpoint.trim().isNotEmpty;

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
            Uri.parse(endpoint),
            headers: const <String, String>{'Content-Type': 'application/json'},
            body: jsonEncode(<String, Object?>{
              'model': model,
              'messages': <Object?>[
                <String, Object?>{
                  'role': 'system',
                  'content':
                      'You are a defense-only cybersecurity risk analyst. Never provide exploit steps, phishing copy, credential theft instructions, or physical intrusion instructions.',
                },
                <String, Object?>{'role': 'user', 'content': policyPrompt},
              ],
              'temperature': 0.15,
              'max_tokens': 900,
              'response_format': <String, Object?>{'type': 'json_object'},
            }),
          )
          .timeout(const Duration(seconds: 120));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('Gemma local HTTP ${response.statusCode}: ${response.body}');
      }
      final decoded = jsonDecode(response.body) as Map<String, Object?>;
      return parseOpinion(
        provider: provider,
        model: model,
        text: extractChatCompletionsText(decoded),
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
