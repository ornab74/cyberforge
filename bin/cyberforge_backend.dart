import 'dart:convert';
import 'dart:io';

/// CyberForge's native Dart control-plane service.
///
/// This service owns orchestration and provider routing. The optional Python
/// process is restricted to llama.cpp inference and listens on loopback only.
Future<void> main(List<String> arguments) async {
  final host = InternetAddress.loopbackIPv4;
  final port = int.tryParse(
        Platform.environment['CYBERFORGE_BACKEND_PORT'] ?? '8788',
      ) ??
      8788;
  final server = await HttpServer.bind(host, port, shared: false);
  stdout.writeln('CyberForge Dart backend listening on http://${host.address}:$port');

  await for (final request in server) {
    try {
      await _route(request);
    } on Object catch (error, stackTrace) {
      stderr.writeln('$error\n$stackTrace');
      await _json(request.response, HttpStatus.internalServerError, {
        'detail': 'Internal backend failure.',
        'requestId': request.headers.value('x-request-id'),
      });
    }
  }
}

Future<void> _route(HttpRequest request) async {
  request.response.headers
    ..set(HttpHeaders.cacheControlHeader, 'no-store')
    ..set('x-content-type-options', 'nosniff')
    ..set('x-frame-options', 'DENY');

  if (request.method == 'GET' && request.uri.path == '/health') {
    return _json(request.response, HttpStatus.ok, {
      'status': 'ok',
      'backend': 'dart',
      'version': '4.0.0-migration',
      'loopbackOnly': true,
      'pythonRole': 'optional-llama-inference-worker',
    });
  }

  if (request.method == 'GET' && request.uri.path == '/v1/runtime/status') {
    return _json(request.response, HttpStatus.ok, {
      'controlPlane': 'dart',
      'providerKeysAcceptedFromEnvironment': false,
      'localWorker': {
        'kind': 'llama-cpp-python',
        'endpoint': 'http://127.0.0.1:8791',
        'isolation': 'loopback subprocess',
      },
    });
  }

  if (request.method == 'POST' && request.uri.path == '/v1/providers/meta/test') {
    final payload = await _body(request);
    final key = payload['apiKey']?.toString().trim() ?? '';
    if (key.isEmpty) {
      return _json(request.response, HttpStatus.badRequest, {
        'detail': 'A Meta Model API key is required for this one-time test.',
      });
    }
    final result = await _testMeta(key);
    return _json(request.response, HttpStatus.ok, result);
  }

  if (request.method == 'POST' && request.uri.path == '/v1/setup/validate') {
    final payload = await _body(request);
    final recoveryLength = payload['recoveryKeyLength'] as int? ?? 0;
    final localModels = payload['localModels'] == true;
    return _json(request.response, HttpStatus.ok, {
      'valid': recoveryLength >= 20,
      'checks': {
        'recoveryKey': recoveryLength >= 20,
        'localModels': localModels ? 'requested' : 'disabled',
        'remoteModelsDefault': false,
      },
    });
  }

  await _json(request.response, HttpStatus.notFound, {
    'detail': 'Endpoint not implemented by the Dart migration service.',
    'path': request.uri.path,
  });
}

Future<Map<String, dynamic>> _testMeta(String apiKey) async {
  final client = HttpClient()..connectionTimeout = const Duration(seconds: 15);
  try {
    final request = await client.postUrl(
      Uri.parse('https://api.meta.ai/v1/responses'),
    );
    request.headers
      ..set(HttpHeaders.authorizationHeader, 'Bearer $apiKey')
      ..contentType = ContentType.json;
    request.write(jsonEncode({
      'model': 'muse-spark-1.1',
      'input': 'Reply with exactly: CYBERFORGE_META_OK',
      'store': false,
    }));
    final response = await request.close().timeout(const Duration(seconds: 45));
    final body = await utf8.decoder.bind(response).join();
    if (response.statusCode < 200 || response.statusCode >= 300) {
      return {
        'ok': false,
        'statusCode': response.statusCode,
        'detail': _safeProviderError(body),
      };
    }
    return {
      'ok': true,
      'provider': 'meta',
      'model': 'muse-spark-1.1',
    };
  } finally {
    client.close(force: true);
  }
}

Future<Map<String, dynamic>> _body(HttpRequest request) async {
  final raw = await utf8.decoder.bind(request).join();
  if (raw.length > 64 * 1024) throw const FormatException('Request too large.');
  if (raw.trim().isEmpty) return <String, dynamic>{};
  final decoded = jsonDecode(raw);
  if (decoded is! Map) throw const FormatException('Expected a JSON object.');
  return decoded.map((key, value) => MapEntry(key.toString(), value));
}

String _safeProviderError(String body) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is Map) {
      return decoded['error']?.toString() ?? decoded['detail']?.toString() ??
          'Provider rejected the request.';
    }
  } on FormatException {
    // Never echo an arbitrary provider page or reflected request data.
  }
  return 'Provider rejected the request.';
}

Future<void> _json(
  HttpResponse response,
  int statusCode,
  Map<String, Object?> body,
) async {
  response
    ..statusCode = statusCode
    ..headers.contentType = ContentType.json
    ..write(jsonEncode(body));
  await response.close();
}
