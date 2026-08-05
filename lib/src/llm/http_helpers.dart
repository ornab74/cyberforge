import 'dart:convert';

String extractResponsesApiText(Map<String, Object?> json) {
  final direct = json['output_text'];
  if (direct is String && direct.isNotEmpty) return direct;
  final output = json['output'];
  if (output is List) {
    final buffer = StringBuffer();
    for (final item in output.whereType<Map>()) {
      final content = item['content'];
      if (content is List) {
        for (final part in content.whereType<Map>()) {
          final text = part['text'];
          if (text is String) buffer.writeln(text);
        }
      }
    }
    if (buffer.isNotEmpty) return buffer.toString().trim();
  }
  return jsonEncode(json);
}

String extractChatCompletionsText(Map<String, Object?> json) {
  final choices = json['choices'];
  if (choices is List && choices.isNotEmpty && choices.first is Map) {
    final message = (choices.first as Map)['message'];
    if (message is Map && message['content'] is String) {
      return message['content'] as String;
    }
  }
  return jsonEncode(json);
}

String extractGeminiText(Map<String, Object?> json) {
  final candidates = json['candidates'];
  if (candidates is List && candidates.isNotEmpty && candidates.first is Map) {
    final content = (candidates.first as Map)['content'];
    if (content is Map && content['parts'] is List) {
      return (content['parts'] as List)
          .whereType<Map>()
          .map((part) => part['text'])
          .whereType<String>()
          .join('\n');
    }
  }
  return jsonEncode(json);
}
