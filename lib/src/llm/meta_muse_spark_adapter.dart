import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';
import 'llm_adapter.dart';

/// Meta Muse Spark 1.1 adapter through the OpenAI-compatible Meta Model API.
final class MetaMuseSparkAdapter implements LlmAdapter {
  MetaMuseSparkAdapter({
    required this.apiKey,
    this.model = 'muse-spark-1.1',
    this.baseUrl = 'https://api.meta.ai/v1',
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String apiKey;
  @override
  final String model;
  final String baseUrl;
  final http.Client _client;

  @override
  ModelProvider get provider => ModelProvider.metaMuse;

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
            Uri.parse('$baseUrl/responses'),
            headers: <String, String>{
              'Authorization': 'Bearer ${apiKey.trim()}',
              'Content-Type': 'application/json',
            },
            body: jsonEncode(<String, Object?>{
              'model': model,
              'input': policyPrompt,
              'reasoning': <String, Object?>{'effort': 'medium'},
              'store': false,
            }),
          )
          .timeout(const Duration(seconds: 90));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError(
          'Meta Model API HTTP ${response.statusCode}: ${response.body}',
        );
      }
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      return parseOpinion(
        provider: provider,
        model: model,
        text: _extractText(decoded),
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

  String _extractText(Map<String, dynamic> payload) {
    final direct = payload['output_text'];
    if (direct is String && direct.isNotEmpty) return direct;
    final output = payload['output'];
    if (output is List) {
      final fragments = <String>[];
      for (final item in output.whereType<Map>()) {
        final content = item['content'];
        if (content is List) {
          for (final part in content.whereType<Map>()) {
            final text = part['text'];
            if (text is String) fragments.add(text);
          }
        }
      }
      if (fragments.isNotEmpty) return fragments.join('\n');
    }
    throw const FormatException('Meta response contained no text output.');
  }
}
