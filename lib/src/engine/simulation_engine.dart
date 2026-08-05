import 'dart:math' as math;

import '../domain/models.dart';
import '../security/authorization_policy.dart';
import 'attack_surface_graph.dart';
import 'gamma_compute_fabric.dart';
import 'risk_engine.dart';

final class SimulationException implements Exception {
  const SimulationException(this.message);
  final String message;
  @override
  String toString() => 'SimulationException: $message';
}

final class SimulationEngine {
  const SimulationEngine({
    this.riskEngine = const RiskEngine(),
    this.fabric = const GammaComputeFabric(),
    this.authorizationPolicy = const AuthorizationPolicy(),
  });

  final RiskEngine riskEngine;
  final GammaComputeFabric fabric;
  final AuthorizationPolicy authorizationPolicy;

  Future<SimulationReport> run(
    SimulationScenario scenario, {
    int iterations = 6000,
  }) async {
    final decision = authorizationPolicy.evaluate(scenario);
    if (!decision.allowed) {
      throw SimulationException(decision.reasons.join(' '));
    }
    if (iterations < 500 || iterations > 100000) {
      throw const SimulationException(
        'Iterations must be between 500 and 100000.',
      );
    }

    final stopwatch = Stopwatch()..start();
    final session = fabric.open(seed: scenario.seed, iterations: iterations);
    final graph = AttackSurfaceGraph(scenario);
    final findingAccumulators = <_FindingKey, _Accumulator>{};
    final assetsById = <String, CyberAsset>{
      for (final asset in scenario.assets) asset.id: asset,
    };
    final hourlyHits = <int, double>{
      for (var hour = 0; hour < 24; hour++) hour: 0,
    };
    final locationHits = <String, double>{};
    final assetPriors = <String, Map<ThreatVector, double>>{};
    for (final asset in scenario.assets) {
      assetPriors[asset.id] = <ThreatVector, double>{
        for (final vector in _vectorsForAsset(asset))
          vector: riskEngine.assetPrior(
            scenario,
            asset,
            vector,
            graph: graph,
          ),
      };
    }
    final humanPriors = <String, Map<ThreatVector, double>>{};
    for (final human in scenario.humans) {
      humanPriors[human.id] = <ThreatVector, double>{
        for (final vector in _humanVectors)
          vector: riskEngine.humanPrior(human, vector),
      };
    }
    final edgeModels = scenario.edges.map((edge) {
      final source = assetsById[edge.fromId];
      final target = assetsById[edge.toId];
      if (source == null || target == null) return null;
      return _EdgeModel(
        edge: edge,
        source: source,
        target: target,
        sourcePrior: riskEngine.assetPrior(
          scenario,
          source,
          edge.vector,
          graph: graph,
        ),
        targetReduction: riskEngine.controlReduction(
          scenario,
          edge.vector,
          target.id,
        ),
        impact: (_impactForAsset(target, edge.vector) * edge.impactMultiplier)
            .clamp(0.05, 1.0)
            .toDouble(),
      );
    }).whereType<_EdgeModel>().toList(growable: false);

    for (var i = 0; i < iterations; i += 1) {
      for (final asset in scenario.assets) {
        for (final vector in _vectorsForAsset(asset)) {
          final prior = assetPriors[asset.id]![vector]!;
          final temporal = _temporalMultiplier(vector, i % 24);
          final probability = (prior * temporal + session.jitter(magnitude: 0.025))
              .clamp(0.001, 0.995)
              .toDouble();
          if (session.sample(probability) > 0) {
            final key = _FindingKey(asset.id, vector);
            final accumulator = findingAccumulators.putIfAbsent(
              key,
              () => _Accumulator(),
            );
            accumulator.hits += 1;
            accumulator.impactSum += _impactForAsset(asset, vector);
            final hour = i % 24;
            hourlyHits[hour] = (hourlyHits[hour] ?? 0) + 1;
            locationHits[asset.location] =
                (locationHits[asset.location] ?? 0) + 1;
          }
        }
      }

      for (final model in edgeModels) {
        final edge = model.edge;
        final temporal = _temporalMultiplier(edge.vector, i % 24);
        final probability = (edge.baseLikelihood *
                (0.55 + model.sourcePrior * 0.75) *
                (1 - model.targetReduction * 0.60) *
                temporal +
            session.jitter(magnitude: 0.02))
            .clamp(0.001, 0.995)
            .toDouble();
        if (session.sample(probability) > 0) {
          final key = _FindingKey(
            model.target.id,
            edge.vector,
            pathway: model.source.id,
          );
          final accumulator = findingAccumulators.putIfAbsent(
            key,
            () => _Accumulator(),
          );
          accumulator.hits += 1;
          accumulator.impactSum += model.impact;
          final hour = i % 24;
          hourlyHits[hour] = (hourlyHits[hour] ?? 0) + 1;
          locationHits[model.target.location] =
              (locationHits[model.target.location] ?? 0) + 1;
        }
      }

      for (final human in scenario.humans) {
        for (final vector in _humanVectors) {
          final prior = humanPriors[human.id]![vector]!;
          final temporal = _temporalMultiplier(vector, i % 24);
          final probability = (prior * temporal + session.jitter(magnitude: 0.03))
              .clamp(0.001, 0.995)
              .toDouble();
          if (session.sample(probability) > 0) {
            final key = _FindingKey('human:${human.id}', vector);
            final accumulator = findingAccumulators.putIfAbsent(
              key,
              () => _Accumulator(),
            );
            accumulator.hits += 1;
            accumulator.impactSum += human.privileged ? 0.88 : 0.56;
            final hour = i % 24;
            hourlyHits[hour] = (hourlyHits[hour] ?? 0) + 1;
            locationHits[human.location] =
                (locationHits[human.location] ?? 0) + 1;
          }
        }
      }

      if (i % 300 == 0) {
        await Future<void>.delayed(Duration.zero);
      }
    }

    final findings = findingAccumulators.entries.map((entry) {
      final key = entry.key;
      final accumulator = entry.value;
      final probability =
          (accumulator.hits / iterations).clamp(0.0, 1.0).toDouble();
      final impact = accumulator.hits == 0
          ? 0.0
          : accumulator.impactSum / accumulator.hits;
      final asset = scenario.assets
          .where((item) => item.id == key.subjectId)
          .firstOrNull;
      final humanId = key.subjectId.startsWith('human:')
          ? key.subjectId.substring('human:'.length)
          : null;
      final human = humanId == null
          ? null
          : scenario.humans.where((item) => item.id == humanId).firstOrNull;
      final sourceAsset = key.pathway.isEmpty ? null : assetsById[key.pathway];
      final subjectName = asset?.name ?? human?.role ?? key.subjectId;
      final pathwayLabel = sourceAsset == null ? '' : ' via ${sourceAsset.name}';
      final location = asset?.location ?? human?.location ?? 'Unknown';
      final severity = riskEngine.severityFor(probability, impact);
      return RiskFinding(
        id:
            '${scenario.id}:${key.subjectId}:${key.vector.name}:${key.pathway}',
        title: '${_titleFor(key.vector)} — $subjectName$pathwayLabel',
        vector: key.vector,
        severity: severity,
        probability: probability,
        impact: impact,
        confidence: _confidence(iterations, probability, session.coherence),
        assetIds: <String>{
          if (asset != null) asset.id,
          if (sourceAsset != null) sourceAsset.id,
        }.toList(growable: false),
        location: location,
        likelyWindow: _likelyWindow(key.vector),
        rationale: _rationale(
          asset: asset,
          human: human,
          sourceAsset: sourceAsset,
        ),
        recommendations: _recommendations(key.vector),
        assumptions: const <String>[
          'Scenario data is synthetic and covered by the stated authorization boundary.',
          'Probabilities are comparative planning signals, not guarantees.',
          'No exploit execution or live-target probing is performed.',
        ],
      );
    }).where((finding) => finding.probability >= 0.025).toList(growable: false)
      ..sort((a, b) => b.riskScore.compareTo(a.riskScore));

    final maxHourly = hourlyHits.values.fold<double>(
      1,
      (current, value) => math.max(current, value),
    );
    final timelineRisk = hourlyHits.map(
      (hour, hits) => MapEntry(hour, (hits / maxHourly).clamp(0.0, 1.0).toDouble()),
    );
    final maxLocation = locationHits.values.isEmpty
        ? 1.0
        : locationHits.values.fold<double>(
            1,
            (current, value) => math.max(current, value),
          );
    final locationRisk = locationHits.map(
      (location, hits) =>
          MapEntry(
            location,
            (hits / maxLocation).clamp(0.0, 1.0).toDouble(),
          ),
    );
    final overallRisk = findings.isEmpty
        ? 0.0
        : findings.take(12).fold<double>(0, (sum, item) => sum + item.riskScore) /
            math.min(12, findings.length) /
            100;

    stopwatch.stop();
    return SimulationReport(
      scenario: scenario,
      generatedAt: DateTime.now().toUtc(),
      overallRisk: overallRisk.clamp(0.0, 1.0).toDouble(),
      findings: findings,
      timelineRisk: timelineRisk,
      locationRisk: locationRisk,
      telemetry: SimulationTelemetry(
        fabricName: 'Dyson Sphere Gamma 3923929 Coherence Fabric (simulated)',
        simulatedQubitRegister: fabric.config.simulatedQubitRegister,
        parallelWorlds: fabric.config.parallelWorlds,
        coherence: session.coherence,
        iterations: iterations,
        elapsedMilliseconds: stopwatch.elapsedMilliseconds,
        seed: scenario.seed,
      ),
      defensiveSummary: _summary(findings),
    );
  }

  static const List<ThreatVector> _humanVectors = <ThreatVector>[
    ThreatVector.phishing,
    ThreatVector.credentialExposure,
    ThreatVector.socialEngineering,
    ThreatVector.insiderRisk,
  ];

  Iterable<ThreatVector> _vectorsForAsset(CyberAsset asset) sync* {
    yield ThreatVector.credentialExposure;
    yield ThreatVector.misconfiguration;
    yield ThreatVector.availability;
    if (asset.kind == AssetKind.endpoint || asset.kind == AssetKind.server) {
      yield ThreatVector.malware;
      yield ThreatVector.dataExfiltration;
    }
    if (asset.kind == AssetKind.facility) {
      yield ThreatVector.physicalIntrusion;
    }
    if (asset.kind == AssetKind.supplier) {
      yield ThreatVector.supplyChain;
    }
  }

  double _impactForAsset(CyberAsset asset, ThreatVector vector) {
    final vectorMultiplier = switch (vector) {
      ThreatVector.dataExfiltration => 1.0,
      ThreatVector.credentialExposure => 0.92,
      ThreatVector.availability => 0.82,
      ThreatVector.physicalIntrusion => 0.84,
      ThreatVector.supplyChain => 0.90,
      ThreatVector.malware => 0.86,
      _ => 0.72,
    };
    final privilege = asset.privileged ? 0.12 : 0.0;
    return (asset.criticality * vectorMultiplier + privilege)
        .clamp(0.05, 1.0)
        .toDouble();
  }

  double _temporalMultiplier(ThreatVector vector, int hour) {
    final businessHours = hour >= 8 && hour <= 18;
    final shiftChange = hour == 7 || hour == 15 || hour == 23;
    return switch (vector) {
      ThreatVector.phishing || ThreatVector.socialEngineering =>
        businessHours ? 1.18 : 0.72,
      ThreatVector.physicalIntrusion => shiftChange ? 1.28 : 0.88,
      ThreatVector.credentialExposure => businessHours ? 1.08 : 0.92,
      ThreatVector.insiderRisk => businessHours ? 1.12 : 0.82,
      _ => 1.0,
    };
  }

  String _likelyWindow(ThreatVector vector) => switch (vector) {
        ThreatVector.phishing || ThreatVector.socialEngineering =>
          '08:00–18:00 local time, strongest near high-workload periods',
        ThreatVector.physicalIntrusion =>
          'Shift changes and visitor-heavy access windows',
        ThreatVector.insiderRisk =>
          'Normal working hours with elevated access activity',
        _ => 'Continuous exposure; prioritize control drift monitoring',
      };

  String _titleFor(ThreatVector vector) => switch (vector) {
        ThreatVector.phishing => 'Phishing susceptibility',
        ThreatVector.credentialExposure => 'Credential or key exposure',
        ThreatVector.socialEngineering => 'Social-engineering pressure',
        ThreatVector.physicalIntrusion => 'Physical access weakness',
        ThreatVector.insiderRisk => 'Insider-risk signal',
        ThreatVector.supplyChain => 'Supplier compromise propagation',
        ThreatVector.misconfiguration => 'Security control drift',
        ThreatVector.malware => 'Malware foothold potential',
        ThreatVector.dataExfiltration => 'Data-loss pathway',
        ThreatVector.availability => 'Service disruption risk',
      };

  String _rationale({
    CyberAsset? asset,
    HumanProfile? human,
    CyberAsset? sourceAsset,
  }) {
    if (sourceAsset != null && asset != null) {
      return 'The modeled ${sourceAsset.name} to ${asset.name} trust relationship combines edge likelihood, source exposure, target control coverage, temporal pressure, and impact propagation.';
    }
    if (human != null) {
      return 'The synthetic profile combines training strength, workload, external contact, privilege, remote-work exposure, and phishing-resistant authentication coverage.';
    }
    return 'The modeled asset combines criticality, privilege, external exposure, control coverage, graph reachability, and vector-specific priors.';
  }

  List<String> _recommendations(ThreatVector vector) => switch (vector) {
        ThreatVector.phishing => const <String>[
            'Prioritize phishing-resistant passkeys for high-risk roles.',
            'Use just-in-time training triggered by risky workflow patterns.',
            'Measure reporting speed, not only click rate.',
          ],
        ThreatVector.credentialExposure => const <String>[
            'Move secrets into a managed vault with short-lived credentials.',
            'Rotate keys according to privilege and observed access frequency.',
            'Detect anomalous secret reads and impossible travel.',
          ],
        ThreatVector.physicalIntrusion => const <String>[
            'Strengthen visitor escort and badge anti-passback controls.',
            'Review camera coverage at shift-change chokepoints.',
            'Run non-confrontational tailgating awareness drills.',
          ],
        ThreatVector.insiderRisk => const <String>[
            'Apply least privilege and time-bound elevation.',
            'Alert on unusual bulk access while protecting employee privacy.',
            'Use peer-reviewed response procedures before escalation.',
          ],
        ThreatVector.supplyChain => const <String>[
            'Inventory supplier trust relationships and inherited permissions.',
            'Require signed artifacts and provenance attestations.',
            'Segment supplier access from production identities.',
          ],
        ThreatVector.misconfiguration => const <String>[
            'Continuously compare deployed controls with policy-as-code.',
            'Require review for high-impact configuration drift.',
          ],
        ThreatVector.malware => const <String>[
            'Harden endpoints and validate detection coverage with safe test events.',
            'Limit lateral movement using segmentation and application control.',
          ],
        ThreatVector.dataExfiltration => const <String>[
            'Classify sensitive data and monitor unusual transfer volume.',
            'Use scoped service identities and egress controls.',
          ],
        ThreatVector.availability => const <String>[
            'Exercise restoration paths and measure recovery objectives.',
            'Remove single points of failure from critical workflows.',
          ],
        ThreatVector.socialEngineering => const <String>[
            'Create callback verification for unusual requests.',
            'Normalize stopping work to verify high-pressure requests.',
          ],
      };

  double _confidence(int iterations, double probability, double coherence) {
    final sampleStrength = 1 - math.exp(-iterations / 3500);
    final uncertaintyPenalty = 1 - (0.5 - probability).abs() * 0.25;
    return (sampleStrength * 0.62 + coherence * 0.28 + uncertaintyPenalty * 0.10)
        .clamp(0.0, 0.99)
        .toDouble();
  }

  String _summary(List<RiskFinding> findings) {
    if (findings.isEmpty) {
      return 'No material signals crossed the reporting threshold. Continue monitoring control drift and scenario quality.';
    }
    final top = findings.take(3).map((item) => item.title).join(', ');
    return 'The strongest modeled defensive priorities are $top. Treat these as ranked planning signals, validate them against telemetry, and address identity controls before expanding simulation scope.';
  }
}

final class _EdgeModel {
  const _EdgeModel({
    required this.edge,
    required this.source,
    required this.target,
    required this.sourcePrior,
    required this.targetReduction,
    required this.impact,
  });

  final AttackSurfaceEdge edge;
  final CyberAsset source;
  final CyberAsset target;
  final double sourcePrior;
  final double targetReduction;
  final double impact;
}

final class _FindingKey {
  const _FindingKey(
    this.subjectId,
    this.vector, {
    this.pathway = '',
  });

  final String subjectId;
  final ThreatVector vector;
  final String pathway;

  @override
  bool operator ==(Object other) =>
      other is _FindingKey &&
      other.subjectId == subjectId &&
      other.vector == vector &&
      other.pathway == pathway;

  @override
  int get hashCode => Object.hash(subjectId, vector, pathway);
}

final class _Accumulator {
  var hits = 0;
  var impactSum = 0.0;
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    if (!iterator.moveNext()) return null;
    return iterator.current;
  }
}
