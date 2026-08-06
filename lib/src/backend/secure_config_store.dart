import 'dart:convert';
import 'dart:io';

/// Stores startup configuration in a restricted local file.
///
/// Uses `~/.local/share/cyberforge/app_secure_config.json` (mode 0600) so the
/// desktop app works without a system keyring / secret-service session. Secrets
/// are still kept out of logs, process arguments, and scenario JSON.
final class SecureConfigStore {
  SecureConfigStore({Directory? dataDir})
      : _file = File(
          '${(dataDir ?? _defaultDataDir()).path}/app_secure_config.json',
        );

  final File _file;

  static const _prefix = 'cyberforge.config.';
  static const _setupCompleteKey = '${_prefix}setup_complete';
  static const _metadataKey = '${_prefix}metadata';
  static const _guideCompleteKey = '${_prefix}advanced_guide_complete';

  static Directory _defaultDataDir() {
    final home = Platform.environment['HOME'] ?? Directory.current.path;
    final dir = Directory('$home/.local/share/cyberforge');
    if (!dir.existsSync()) {
      dir.createSync(recursive: true);
    }
    return dir;
  }

  Future<Map<String, String>> _readAll() async {
    try {
      if (!await _file.exists()) return <String, String>{};
      final raw = await _file.readAsString();
      if (raw.trim().isEmpty) return <String, String>{};
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return <String, String>{};
      return decoded.map(
        (key, value) => MapEntry(key.toString(), value?.toString() ?? ''),
      );
    } on Object {
      return <String, String>{};
    }
  }

  Future<void> _writeAll(Map<String, String> data) async {
    await _file.parent.create(recursive: true);
    await _file.writeAsString(jsonEncode(data), flush: true);
    try {
      await Process.run('chmod', ['600', _file.path]);
    } on Object {
      // Best-effort permissions on platforms without chmod.
    }
  }

  Future<String?> _read(String key) async => (await _readAll())[key];

  Future<void> _write(String key, String value) async {
    final data = await _readAll();
    data[key] = value;
    await _writeAll(data);
  }

  Future<void> _delete(String key) async {
    final data = await _readAll();
    data.remove(key);
    await _writeAll(data);
  }

  Future<bool> isSetupComplete() async =>
      await _read(_setupCompleteKey) == 'true';

  Future<void> writeSecret(String logicalName, String value) async {
    final normalized = logicalName.trim().toLowerCase();
    if (normalized.isEmpty) throw ArgumentError.value(logicalName, 'logicalName');
    if (value.trim().isEmpty) {
      await deleteSecret(normalized);
      return;
    }
    await _write('$_prefix$normalized', value.trim());
  }

  Future<String?> readSecret(String logicalName) =>
      _read('$_prefix${logicalName.trim().toLowerCase()}');

  Future<void> deleteSecret(String logicalName) =>
      _delete('$_prefix${logicalName.trim().toLowerCase()}');

  Future<void> saveMetadata(Map<String, Object?> metadata) async {
    final safe = <String, Object?>{
      ...metadata,
      'savedAt': DateTime.now().toUtc().toIso8601String(),
    };
    await _write(_metadataKey, jsonEncode(safe));
  }

  Future<Map<String, dynamic>> metadata() async {
    final raw = await _read(_metadataKey);
    if (raw == null || raw.isEmpty) return <String, dynamic>{};
    final decoded = jsonDecode(raw);
    return decoded is Map
        ? decoded.map((key, value) => MapEntry(key.toString(), value))
        : <String, dynamic>{};
  }

  Future<void> markSetupComplete() => _write(_setupCompleteKey, 'true');

  Future<bool> isAdvancedGuideComplete() async =>
      await _read(_guideCompleteKey) == 'true';

  Future<void> markAdvancedGuideComplete() =>
      _write(_guideCompleteKey, 'true');

  /// Vault password used for every-boot unlock when device key is unavailable.
  Future<String?> vaultPassword() async {
    final primary = await readSecret('vault_password');
    if (primary != null && primary.isNotEmpty) return primary;
    return readSecret('vault_recovery_key');
  }

  Future<void> reset() async {
    final keys = <String>[
      _setupCompleteKey,
      _metadataKey,
      _guideCompleteKey,
      '${_prefix}vault_recovery_key',
      '${_prefix}vault_password',
      '${_prefix}meta_model_api_key',
      '${_prefix}openai_api_key',
      '${_prefix}xai_api_key',
      '${_prefix}gemini_api_key',
      '${_prefix}digitalocean_api_key',
    ];
    final data = await _readAll();
    for (final key in keys) {
      data.remove(key);
    }
    await _writeAll(data);
  }
}
