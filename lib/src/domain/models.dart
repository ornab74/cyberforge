import 'dart:convert';

enum AssetKind {
  identity,
  credential,
  endpoint,
  server,
  cloudService,
  application,
  facility,
  supplier,
  dataStore,
  networkZone,
}

enum ThreatVector {
  phishing,
  credentialExposure,
  socialEngineering,
  physicalIntrusion,
  insiderRisk,
  supplyChain,
  misconfiguration,
  malware,
  dataExfiltration,
  availability,
}

enum Severity { informational, low, medium, high, critical }

enum ControlType {
  mfa,
  passkey,
  keyRotation,
  leastPrivilege,
  segmentation,
  endpointDetection,
  emailSecurity,
  userTraining,
  visitorManagement,
  badgeAntiPassback,
  cameraCoverage,
  secretsVault,
  backupRecovery,
  supplierAssurance,
  monitoring,
}

final class CyberAsset {
  const CyberAsset({
    required this.id,
    required this.name,
    required this.kind,
    required this.location,
    required this.criticality,
    this.tags = const <String>[],
    this.ownerRole = 'Unassigned',
    this.internetExposed = false,
    this.privileged = false,
    this.metadata = const <String, Object?>{},
  });

  final String id;
  final String name;
  final AssetKind kind;
  final String location;
  final double criticality;
  final List<String> tags;
  final String ownerRole;
  final bool internetExposed;
  final bool privileged;
  final Map<String, Object?> metadata;

  factory CyberAsset.fromJson(Map<String, Object?> json) => CyberAsset(
        id: json['id']! as String,
        name: json['name']! as String,
        kind: AssetKind.values.byName(json['kind']! as String),
        location: json['location']! as String,
        criticality: (json['criticality']! as num).toDouble(),
        tags: List<String>.from(json['tags'] as List? ?? const []),
        ownerRole: json['ownerRole'] as String? ?? 'Unassigned',
        internetExposed: json['internetExposed'] as bool? ?? false,
        privileged: json['privileged'] as bool? ?? false,
        metadata: Map<String, Object?>.from(
          json['metadata'] as Map? ?? const <String, Object?>{},
        ),
      );

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'name': name,
        'kind': kind.name,
        'location': location,
        'criticality': criticality,
        'tags': tags,
        'ownerRole': ownerRole,
        'internetExposed': internetExposed,
        'privileged': privileged,
        'metadata': metadata,
      };
}

final class SecurityControl {
  const SecurityControl({
    required this.id,
    required this.name,
    required this.type,
    required this.effectiveness,
    required this.coverage,
    this.assetIds = const <String>[],
    this.notes = '',
  });

  final String id;
  final String name;
  final ControlType type;
  final double effectiveness;
  final double coverage;
  final List<String> assetIds;
  final String notes;

  factory SecurityControl.fromJson(Map<String, Object?> json) => SecurityControl(
        id: json['id']! as String,
        name: json['name']! as String,
        type: ControlType.values.byName(json['type']! as String),
        effectiveness: (json['effectiveness']! as num).toDouble(),
        coverage: (json['coverage']! as num).toDouble(),
        assetIds: List<String>.from(json['assetIds'] as List? ?? const []),
        notes: json['notes'] as String? ?? '',
      );

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'name': name,
        'type': type.name,
        'effectiveness': effectiveness,
        'coverage': coverage,
        'assetIds': assetIds,
        'notes': notes,
      };
}

final class HumanProfile {
  const HumanProfile({
    required this.id,
    required this.role,
    required this.location,
    required this.trainingScore,
    required this.workload,
    required this.externalContactRate,
    this.privileged = false,
    this.remoteWorker = false,
    this.mfaEnabled = true,
    this.passkeyEnabled = false,
  });

  final String id;
  final String role;
  final String location;
  final double trainingScore;
  final double workload;
  final double externalContactRate;
  final bool privileged;
  final bool remoteWorker;
  final bool mfaEnabled;
  final bool passkeyEnabled;

  factory HumanProfile.fromJson(Map<String, Object?> json) => HumanProfile(
        id: json['id']! as String,
        role: json['role']! as String,
        location: json['location']! as String,
        trainingScore: (json['trainingScore']! as num).toDouble(),
        workload: (json['workload']! as num).toDouble(),
        externalContactRate: (json['externalContactRate']! as num).toDouble(),
        privileged: json['privileged'] as bool? ?? false,
        remoteWorker: json['remoteWorker'] as bool? ?? false,
        mfaEnabled: json['mfaEnabled'] as bool? ?? true,
        passkeyEnabled: json['passkeyEnabled'] as bool? ?? false,
      );

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'role': role,
        'location': location,
        'trainingScore': trainingScore,
        'workload': workload,
        'externalContactRate': externalContactRate,
        'privileged': privileged,
        'remoteWorker': remoteWorker,
        'mfaEnabled': mfaEnabled,
        'passkeyEnabled': passkeyEnabled,
      };
}

final class AttackSurfaceEdge {
  const AttackSurfaceEdge({
    required this.fromId,
    required this.toId,
    required this.vector,
    required this.baseLikelihood,
    required this.impactMultiplier,
    this.label = '',
  });

  final String fromId;
  final String toId;
  final ThreatVector vector;
  final double baseLikelihood;
  final double impactMultiplier;
  final String label;

  factory AttackSurfaceEdge.fromJson(Map<String, Object?> json) =>
      AttackSurfaceEdge(
        fromId: json['fromId']! as String,
        toId: json['toId']! as String,
        vector: ThreatVector.values.byName(json['vector']! as String),
        baseLikelihood: (json['baseLikelihood']! as num).toDouble(),
        impactMultiplier: (json['impactMultiplier']! as num).toDouble(),
        label: json['label'] as String? ?? '',
      );

  Map<String, Object?> toJson() => <String, Object?>{
        'fromId': fromId,
        'toId': toId,
        'vector': vector.name,
        'baseLikelihood': baseLikelihood,
        'impactMultiplier': impactMultiplier,
        'label': label,
      };
}

final class SimulationScenario {
  const SimulationScenario({
    required this.id,
    required this.name,
    required this.description,
    required this.authorizationStatement,
    required this.assets,
    required this.controls,
    required this.humans,
    required this.edges,
    this.timeHorizonDays = 30,
    this.seed = 3923929,
    this.synthetic = true,
  });

  final String id;
  final String name;
  final String description;
  final String authorizationStatement;
  final List<CyberAsset> assets;
  final List<SecurityControl> controls;
  final List<HumanProfile> humans;
  final List<AttackSurfaceEdge> edges;
  final int timeHorizonDays;
  final int seed;
  final bool synthetic;

  factory SimulationScenario.fromJson(Map<String, Object?> json) =>
      SimulationScenario(
        id: json['id']! as String,
        name: json['name']! as String,
        description: json['description']! as String,
        authorizationStatement: json['authorizationStatement']! as String,
        assets: (json['assets']! as List)
            .cast<Map>()
            .map((e) => CyberAsset.fromJson(Map<String, Object?>.from(e)))
            .toList(growable: false),
        controls: (json['controls']! as List)
            .cast<Map>()
            .map((e) => SecurityControl.fromJson(Map<String, Object?>.from(e)))
            .toList(growable: false),
        humans: (json['humans']! as List)
            .cast<Map>()
            .map((e) => HumanProfile.fromJson(Map<String, Object?>.from(e)))
            .toList(growable: false),
        edges: (json['edges']! as List)
            .cast<Map>()
            .map((e) => AttackSurfaceEdge.fromJson(Map<String, Object?>.from(e)))
            .toList(growable: false),
        timeHorizonDays: json['timeHorizonDays'] as int? ?? 30,
        seed: json['seed'] as int? ?? 3923929,
        synthetic: json['synthetic'] as bool? ?? true,
      );

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'name': name,
        'description': description,
        'authorizationStatement': authorizationStatement,
        'assets': assets.map((e) => e.toJson()).toList(growable: false),
        'controls': controls.map((e) => e.toJson()).toList(growable: false),
        'humans': humans.map((e) => e.toJson()).toList(growable: false),
        'edges': edges.map((e) => e.toJson()).toList(growable: false),
        'timeHorizonDays': timeHorizonDays,
        'seed': seed,
        'synthetic': synthetic,
      };

  String prettyJson() => const JsonEncoder.withIndent('  ').convert(toJson());
}

final class RiskFinding {
  const RiskFinding({
    required this.id,
    required this.title,
    required this.vector,
    required this.severity,
    required this.probability,
    required this.impact,
    required this.confidence,
    required this.assetIds,
    required this.location,
    required this.likelyWindow,
    required this.rationale,
    required this.recommendations,
    this.assumptions = const <String>[],
  });

  final String id;
  final String title;
  final ThreatVector vector;
  final Severity severity;
  final double probability;
  final double impact;
  final double confidence;
  final List<String> assetIds;
  final String location;
  final String likelyWindow;
  final String rationale;
  final List<String> recommendations;
  final List<String> assumptions;

  double get riskScore => probability * impact * 100;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'title': title,
        'vector': vector.name,
        'severity': severity.name,
        'probability': probability,
        'impact': impact,
        'confidence': confidence,
        'assetIds': assetIds,
        'location': location,
        'likelyWindow': likelyWindow,
        'rationale': rationale,
        'recommendations': recommendations,
        'assumptions': assumptions,
        'riskScore': riskScore,
      };
}

final class SimulationTelemetry {
  const SimulationTelemetry({
    required this.fabricName,
    required this.simulatedQubitRegister,
    required this.parallelWorlds,
    required this.coherence,
    required this.iterations,
    required this.elapsedMilliseconds,
    required this.seed,
  });

  final String fabricName;
  final int simulatedQubitRegister;
  final int parallelWorlds;
  final double coherence;
  final int iterations;
  final int elapsedMilliseconds;
  final int seed;

  Map<String, Object?> toJson() => <String, Object?>{
        'fabricName': fabricName,
        'simulatedQubitRegister': simulatedQubitRegister,
        'parallelWorlds': parallelWorlds,
        'coherence': coherence,
        'iterations': iterations,
        'elapsedMilliseconds': elapsedMilliseconds,
        'seed': seed,
        'disclaimer':
            'Quantum-inspired software simulation; no physical quantum or Dyson-sphere hardware is claimed.',
      };
}

final class SimulationReport {
  const SimulationReport({
    required this.scenario,
    required this.generatedAt,
    required this.overallRisk,
    required this.findings,
    required this.timelineRisk,
    required this.locationRisk,
    required this.telemetry,
    required this.defensiveSummary,
  });

  final SimulationScenario scenario;
  final DateTime generatedAt;
  final double overallRisk;
  final List<RiskFinding> findings;
  final Map<int, double> timelineRisk;
  final Map<String, double> locationRisk;
  final SimulationTelemetry telemetry;
  final String defensiveSummary;

  Map<String, Object?> toJson() => <String, Object?>{
        'scenario': scenario.toJson(),
        'generatedAt': generatedAt.toUtc().toIso8601String(),
        'overallRisk': overallRisk,
        'findings': findings.map((e) => e.toJson()).toList(growable: false),
        'timelineRisk': timelineRisk.map((k, v) => MapEntry(k.toString(), v)),
        'locationRisk': locationRisk,
        'telemetry': telemetry.toJson(),
        'defensiveSummary': defensiveSummary,
      };

  String prettyJson() => const JsonEncoder.withIndent('  ').convert(toJson());
}
