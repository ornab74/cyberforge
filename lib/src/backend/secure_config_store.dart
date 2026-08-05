import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Stores startup configuration in the platform keychain/credential vault.
/// Secrets are never written to .env files, logs, process arguments, or app state.
final class SecureConfigStore {
  SecureConfigStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _prefix = 'cyberforge.config.';
  static const _setupCompleteKey = '${_prefix}setup_complete';
  static const _metadataKey = '${_prefix}metadata';

  Future<bool> isSetupComplete() async =>
      await _storage.read(key: _setupCompleteKey) == 'true';

  Future<void> writeSecret(String logicalName, String value) async {
    final normalized = logicalName.trim().toLowerCase();
    if (normalized.isEmpty) throw ArgumentError.value(logicalName, 'logicalName');
    if (value.trim().isEmpty) {
      await deleteSecret(normalized);
      return;
    }
    await _storage.write(key: '$_prefix$normalized', value: value.trim());
  }

  Future<String?> readSecret(String logicalName) =>
      _storage.read(key: '$_prefix${logicalName.trim().toLowerCase()}');

  Future<void> deleteSecret(String logicalName) =>
      _storage.delete(key: '$_prefix${logicalName.trim().toLowerCase()}');

  Future<void> saveMetadata(Map<String, Object?> metadata) async {
    final safe = <String, Object?>{
      ...metadata,
      'savedAt': DateTime.now().toUtc().toIso8601String(),
    };
    await _storage.write(key: _metadataKey, value: jsonEncode(safe));
  }

  Future<Map<String, dynamic>> metadata() async {
    final raw = await _storage.read(key: _metadataKey);
    if (raw == null || raw.isEmpty) return <String, dynamic>{};
    final decoded = jsonDecode(raw);
    return decoded is Map
        ? decoded.map((key, value) => MapEntry(key.toString(), value))
        : <String, dynamic>{};
  }

  Future<void> markSetupComplete() =>
      _storage.write(key: _setupCompleteKey, value: 'true');

  Future<void> reset() async {
    final keys = <String>[
      _setupCompleteKey,
      _metadataKey,
      '${_prefix}vault_recovery_key',
      '${_prefix}meta_model_api_key',
      '${_prefix}openai_api_key',
      '${_prefix}xai_api_key',
      '${_prefix}gemini_api_key',
      '${_prefix}digitalocean_api_key',
    ];
    for (final key in keys) {
      await _storage.delete(key: key);
    }
  }
}
