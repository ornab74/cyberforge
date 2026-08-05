import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'models.dart';

final class SidecarException implements Exception {
  const SidecarException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;

  @override
  String toString() =>
      statusCode == null ? message : 'SidecarException($statusCode): $message';
}

final class CyberForgeSidecarClient {
  CyberForgeSidecarClient({
    this.baseUri = const String.fromEnvironment(
      'CYBERFORGE_SIDECAR_URL',
      defaultValue: 'http://127.0.0.1:8788',
    ),
    http.Client? httpClient,
    FlutterSecureStorage? secureStorage,
  }) : _http = httpClient ?? http.Client(),
       _storage = defaultTargetPlatform == TargetPlatform.linux
           ? null
           : secureStorage ?? const FlutterSecureStorage();

  final String baseUri;
  final http.Client _http;
  final FlutterSecureStorage? _storage;
  String? _memorySessionToken;
  bool _useSystemKeyring = false;
  static const _sessionKey = 'cyberforge-v3-sidecar-session';

  Uri _uri(String path) => Uri.parse('$baseUri$path');

  Future<String?> sessionToken() async {
    if (_memoryOnlySession) return _memorySessionToken;
    try {
      return await _storage!.read(key: _sessionKey);
    } on Object {
      // Some Linux containers (including Crostini) have no Secret Service.
      // Keep only the short-lived sidecar session in memory for this run.
      return _memorySessionToken;
    }
  }

  Future<void> clearSession() async {
    if (_memoryOnlySession) {
      _memorySessionToken = null;
      return;
    }
    try {
      await _storage!.delete(key: _sessionKey);
    } on Object {
      // Memory-only sessions are still cleared when the keyring is absent.
    }
    _memorySessionToken = null;
  }

  Future<CyberForgeHealth> health() async {
    try {
      final response = await _http
          .get(_uri('/health'))
          .timeout(const Duration(seconds: 4));
      return CyberForgeHealth.fromJson(_decode(response));
    } on Object catch (error) {
      return CyberForgeHealth.offline(error.toString());
    }
  }

  Future<Map<String, dynamic>> defaultScenario() async {
    final response = await _http
        .get(_uri('/v1/scenarios/default'))
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<ScanReport> scan(Map<String, dynamic> packet) async {
    final headers = await _headers(auth: packet['includeRemoteModels'] == true);
    final response = await _http
        .post(_uri('/v1/scan'), headers: headers, body: jsonEncode(packet))
        .timeout(const Duration(minutes: 8));
    return ScanReport(_decode(response));
  }

  Future<SimcomResponse> simcom(
    String command, {
    Map<String, dynamic>? packet,
  }) async {
    final response = await _http
        .post(
          _uri('/v1/simcom'),
          headers: const <String, String>{'Content-Type': 'application/json'},
          body: jsonEncode(<String, dynamic>{
            'command': command,
            if (packet != null) 'packet': packet,
          }),
        )
        .timeout(const Duration(minutes: 3));
    return SimcomResponse.fromJson(_decode(response));
  }

  Future<void> createVault(String password) async {
    final response = await _http.post(
      _uri('/v1/vault/create'),
      headers: const <String, String>{'Content-Type': 'application/json'},
      body: jsonEncode(<String, dynamic>{
        'password': password,
        'password_required': true,
      }),
    );
    await _saveSession(_decode(response));
  }

  Future<void> unlockVault(String password) async {
    final response = await _http.post(
      _uri('/v1/vault/unlock'),
      headers: const <String, String>{'Content-Type': 'application/json'},
      body: jsonEncode(<String, dynamic>{
        'password': password,
        'password_required': true,
      }),
    );
    await _saveSession(_decode(response));
  }

  Future<void> lockVault() async {
    final response = await _http.post(
      _uri('/v1/vault/lock'),
      headers: await _headers(auth: true),
    );
    _decode(response);
    await clearSession();
  }

  Future<void> setProviderSecret(String provider, String secret) async {
    final response = await _http.post(
      _uri('/v1/vault/providers'),
      headers: await _headers(auth: true),
      body: jsonEncode(<String, dynamic>{
        'provider': provider,
        'secret': secret,
      }),
    );
    _decode(response);
  }

  Future<Map<String, dynamic>> rotateVaultKey() async {
    final response = await _http.post(
      _uri('/v1/vault/rotate'),
      headers: await _headers(auth: true),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> installModel(String profileId) async {
    final response = await _http.post(
      _uri('/v1/models/install'),
      headers: await _headers(auth: true),
      body: jsonEncode(<String, dynamic>{'profile_id': profileId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> importLocalModel(
    String profileId,
    String sourcePath,
  ) async {
    final response = await _http.post(
      _uri('/v1/models/import'),
      headers: await _headers(auth: true),
      body: jsonEncode(<String, dynamic>{
        'profile_id': profileId,
        'source_path': sourcePath,
      }),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> loadModel(String profileId) async {
    final response = await _http.post(
      _uri('/v1/models/load'),
      headers: await _headers(auth: true),
      body: jsonEncode(<String, dynamic>{'profile_id': profileId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> unloadModel(String profileId) async {
    final response = await _http.post(
      _uri('/v1/models/unload'),
      headers: await _headers(auth: true),
      body: jsonEncode(<String, dynamic>{'profile_id': profileId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> captureNews(
    String query, {
    String provider = 'xai',
  }) async {
    final response = await _http.post(
      _uri('/v1/news/capture'),
      headers: await _headers(auth: true),
      body: jsonEncode(<String, dynamic>{'query': query, 'provider': provider}),
    );
    return _decode(response);
  }

  Future<Map<String, String>> _headers({required bool auth}) async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (auth) {
      final token = await sessionToken();
      if (token == null || token.isEmpty) {
        throw const SidecarException('Unlock the local provider vault first.');
      }
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<void> _saveSession(Map<String, dynamic> response) async {
    final token = response['sessionToken']?.toString();
    if (token == null || token.isEmpty) {
      throw const SidecarException('Sidecar did not return a vault session.');
    }
    if (_memoryOnlySession) {
      _memorySessionToken = token;
      return;
    }
    try {
      await _storage!.write(key: _sessionKey, value: token);
    } on Object catch (error) {
      _memorySessionToken = token;
    }
  }

  bool get usesSystemKeyring => _useSystemKeyring;

  void setStorageMode({required bool useSystemKeyring}) {
    _useSystemKeyring = useSystemKeyring;
  }

  bool get _memoryOnlySession =>
      defaultTargetPlatform == TargetPlatform.linux && !_useSystemKeyring;

  Map<String, dynamic> _decode(http.Response response) {
    Map<String, dynamic> decoded;
    try {
      final value = jsonDecode(response.body);
      decoded = value is Map
          ? value.map(
              (dynamic key, dynamic item) => MapEntry(key.toString(), item),
            )
          : <String, dynamic>{'value': value};
    } on FormatException {
      decoded = <String, dynamic>{'detail': response.body};
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SidecarException(
        decoded['detail']?.toString() ?? 'Sidecar request failed.',
        statusCode: response.statusCode,
      );
    }
    return decoded;
  }
}
