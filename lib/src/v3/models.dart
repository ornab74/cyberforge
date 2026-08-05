import 'dart:convert';

final class CyberForgeHealth {
  const CyberForgeHealth({
    required this.online,
    required this.version,
    required this.vaultUnlocked,
    required this.vaultExists,
    required this.postQuantumAvailable,
    required this.models,
    required this.council,
    this.error,
  });

  final bool online;
  final String version;
  final bool vaultUnlocked;
  final bool vaultExists;
  final bool postQuantumAvailable;
  final List<Map<String, dynamic>> models;
  final List<Map<String, dynamic>> council;
  final String? error;

  factory CyberForgeHealth.offline([String? error]) => CyberForgeHealth(
    online: false,
    version: 'offline',
    vaultUnlocked: false,
    vaultExists: false,
    postQuantumAvailable: false,
    models: const <Map<String, dynamic>>[],
    council: const <Map<String, dynamic>>[],
    error: error,
  );

  factory CyberForgeHealth.fromJson(Map<String, dynamic> json) {
    final vault = _map(json['vault']);
    final pq = _map(json['postQuantum']);
    return CyberForgeHealth(
      online: json['status'] == 'ok',
      version: json['version']?.toString() ?? 'unknown',
      vaultUnlocked: vault['unlocked'] == true,
      vaultExists: vault['exists'] == true,
      postQuantumAvailable: pq['available'] == true,
      models: _mapList(json['models']),
      council: _mapList(json['council']),
    );
  }
}

final class ScanReport {
  const ScanReport(this.raw);
  final Map<String, dynamic> raw;

  double get overallRisk => _double(raw['overallRisk']);
  String get summary => raw['summary']?.toString() ?? 'No report generated.';
  String get generatedAt => raw['generatedAt']?.toString() ?? '';
  String get name => raw['name']?.toString() ?? 'CyberForge scan';
  String get packetDigest => raw['packetDigest']?.toString() ?? '';
  Map<String, dynamic> get telemetry => _map(raw['telemetry']);
  Map<String, dynamic> get impact => _map(raw['impactEstimate']);
  Map<String, dynamic> get dimensions => _map(raw['dimensionScores']);
  List<Map<String, dynamic>> get findings => _mapList(raw['findings']);
  List<Map<String, dynamic>> get hotspots => _mapList(raw['hotspots']);
  List<Map<String, dynamic>> get timeline => _mapList(raw['timeline']);
  List<String> get bootcom =>
      (raw['bootcom'] as List<dynamic>? ?? const <dynamic>[])
          .map((dynamic value) => value.toString())
          .toList(growable: false);
  Map<String, dynamic> get council => _map(raw['council']);

  String prettyJson() => const JsonEncoder.withIndent('  ').convert(raw);
}

final class SimcomResponse {
  const SimcomResponse({required this.command, required this.lines});
  final String command;
  final List<String> lines;

  factory SimcomResponse.fromJson(Map<String, dynamic> json) => SimcomResponse(
    command: json['command']?.toString() ?? '',
    lines: (json['lines'] as List<dynamic>? ?? const <dynamic>[])
        .map((dynamic value) => value.toString())
        .toList(growable: false),
  );
}

Map<String, dynamic> _map(Object? value) => value is Map
    ? value.map((dynamic key, dynamic item) => MapEntry(key.toString(), item))
    : <String, dynamic>{};

List<Map<String, dynamic>> _mapList(Object? value) => value is List
    ? value
          .whereType<Map>()
          .map((Map item) => _map(item))
          .toList(growable: false)
    : const <Map<String, dynamic>>[];

double _double(Object? value) => value is num
    ? value.toDouble()
    : double.tryParse(value?.toString() ?? '') ?? 0;
