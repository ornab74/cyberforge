import 'dart:math' as math;

import '../domain/models.dart';
import 'attack_surface_graph.dart';

final class RiskEngine {
  const RiskEngine();

  double controlReduction(
    SimulationScenario scenario,
    ThreatVector vector,
    String assetId,
  ) {
    final relevant = scenario.controls.where((control) {
      if (control.assetIds.isNotEmpty && !control.assetIds.contains(assetId)) {
        return false;
      }
      return _controlVectors(control.type).contains(vector);
    });
    var residual = 1.0;
    for (final control in relevant) {
      final reduction = control.effectiveness * control.coverage;
      residual *= 1 - reduction.clamp(0.0, 0.92).toDouble();
    }
    return (1 - residual).clamp(0.0, 0.95).toDouble();
  }

  double assetPrior(
    SimulationScenario scenario,
    CyberAsset asset,
    ThreatVector vector, {
    AttackSurfaceGraph? graph,
  }) {
    final attackGraph = graph ?? AttackSurfaceGraph(scenario);
    final exposure = asset.internetExposed ? 0.24 : 0.03;
    final privilege = asset.privileged ? 0.16 : 0.0;
    final blast = attackGraph.blastRadius(asset.id) * 0.18;
    final vectorBase = switch (vector) {
      ThreatVector.phishing => 0.10,
      ThreatVector.credentialExposure => 0.12,
      ThreatVector.socialEngineering => 0.08,
      ThreatVector.physicalIntrusion =>
        asset.kind == AssetKind.facility ? 0.15 : 0.03,
      ThreatVector.insiderRisk => 0.06,
      ThreatVector.supplyChain =>
        asset.kind == AssetKind.supplier ? 0.18 : 0.05,
      ThreatVector.misconfiguration => 0.13,
      ThreatVector.malware => 0.10,
      ThreatVector.dataExfiltration => 0.08,
      ThreatVector.availability => 0.07,
    };
    final reduction = controlReduction(scenario, vector, asset.id);
    return _sigmoid(
      -2.2 +
          vectorBase * 5 +
          exposure * 3 +
          privilege * 2 +
          asset.criticality * 0.5 +
          blast -
          reduction * 2.4,
    );
  }

  double humanPrior(HumanProfile human, ThreatVector vector) {
    final trainingGap = 1 - human.trainingScore.clamp(0.0, 1.0).toDouble();
    final workload = human.workload.clamp(0.0, 1.0).toDouble();
    final contact = human.externalContactRate.clamp(0.0, 1.0).toDouble();
    final privilege = human.privileged ? 0.12 : 0.0;
    final remote = human.remoteWorker ? 0.08 : 0.0;
    final passkey = human.passkeyEnabled ? -0.24 : 0.0;
    final mfa = human.mfaEnabled ? -0.12 : 0.12;
    final vectorWeight = switch (vector) {
      ThreatVector.phishing => 0.32,
      ThreatVector.credentialExposure => 0.26,
      ThreatVector.socialEngineering => 0.29,
      ThreatVector.physicalIntrusion => 0.08,
      ThreatVector.insiderRisk => 0.16,
      _ => 0.05,
    };
    return _sigmoid(
      -2.0 +
          vectorWeight * 3 +
          trainingGap * 1.4 +
          workload * 0.85 +
          contact * 0.75 +
          privilege +
          remote +
          passkey +
          mfa,
    );
  }

  Severity severityFor(double probability, double impact) {
    final score = probability * impact;
    if (score >= 0.68) return Severity.critical;
    if (score >= 0.45) return Severity.high;
    if (score >= 0.24) return Severity.medium;
    if (score >= 0.10) return Severity.low;
    return Severity.informational;
  }

  static final Map<ControlType, Set<ThreatVector>> _coverage = {
    ControlType.mfa: {
      ThreatVector.credentialExposure,
      ThreatVector.phishing,
    },
    ControlType.passkey: {
      ThreatVector.credentialExposure,
      ThreatVector.phishing,
      ThreatVector.socialEngineering,
    },
    ControlType.keyRotation: {ThreatVector.credentialExposure},
    ControlType.leastPrivilege: {
      ThreatVector.insiderRisk,
      ThreatVector.dataExfiltration,
      ThreatVector.malware,
    },
    ControlType.segmentation: {
      ThreatVector.malware,
      ThreatVector.dataExfiltration,
      ThreatVector.availability,
    },
    ControlType.endpointDetection: {
      ThreatVector.malware,
      ThreatVector.dataExfiltration,
    },
    ControlType.emailSecurity: {
      ThreatVector.phishing,
      ThreatVector.socialEngineering,
    },
    ControlType.userTraining: {
      ThreatVector.phishing,
      ThreatVector.socialEngineering,
      ThreatVector.insiderRisk,
    },
    ControlType.visitorManagement: {ThreatVector.physicalIntrusion},
    ControlType.badgeAntiPassback: {ThreatVector.physicalIntrusion},
    ControlType.cameraCoverage: {ThreatVector.physicalIntrusion},
    ControlType.secretsVault: {
      ThreatVector.credentialExposure,
      ThreatVector.dataExfiltration,
    },
    ControlType.backupRecovery: {
      ThreatVector.availability,
      ThreatVector.malware,
    },
    ControlType.supplierAssurance: {ThreatVector.supplyChain},
    ControlType.monitoring: ThreatVector.values.toSet(),
  };

  Set<ThreatVector> _controlVectors(ControlType type) =>
      _coverage[type] ?? const <ThreatVector>{};

  double _sigmoid(double x) => 1 / (1 + math.exp(-x));
}
