import 'dart:convert';
import 'dart:io';

import '../domain/models.dart';

final class ScenarioRepository {
  const ScenarioRepository();

  Future<SimulationScenario> loadFile(String path) async {
    final text = await File(path).readAsString();
    return SimulationScenario.fromJson(
      Map<String, Object?>.from(jsonDecode(text) as Map),
    );
  }

  Future<void> saveFile(SimulationScenario scenario, String path) async {
    await File(path).writeAsString(scenario.prettyJson());
  }

  SimulationScenario demo() => const SimulationScenario(
        id: 'synthetic-health-network-001',
        name: 'Synthetic Regional Care Network',
        description:
            'A fully fictional healthcare and logistics digital twin used to evaluate identity, phishing, secret-management, supplier, and physical-access defenses.',
        authorizationStatement:
            'Authorized synthetic blue-team exercise owned by the CyberForge operator; no live systems or real people are represented.',
        timeHorizonDays: 30,
        seed: 3923929,
        synthetic: true,
        assets: <CyberAsset>[
          CyberAsset(
            id: 'idp',
            name: 'Workforce Identity Provider',
            kind: AssetKind.cloudService,
            location: 'Cloud / us-east',
            criticality: 0.98,
            ownerRole: 'Identity Engineering',
            internetExposed: true,
            privileged: true,
            tags: <String>['identity', 'sso', 'tier-0'],
          ),
          CyberAsset(
            id: 'secrets',
            name: 'Application Secrets Vault',
            kind: AssetKind.credential,
            location: 'Cloud / us-east',
            criticality: 0.96,
            ownerRole: 'Platform Security',
            privileged: true,
            tags: <String>['keys', 'tokens', 'tier-0'],
          ),
          CyberAsset(
            id: 'ehr',
            name: 'Synthetic Patient Record Service',
            kind: AssetKind.application,
            location: 'Primary Data Center',
            criticality: 0.94,
            ownerRole: 'Clinical Applications',
            internetExposed: false,
            privileged: true,
            tags: <String>['regulated-data', 'clinical'],
          ),
          CyberAsset(
            id: 'email',
            name: 'Workforce Email',
            kind: AssetKind.cloudService,
            location: 'Cloud / global',
            criticality: 0.80,
            ownerRole: 'Collaboration Services',
            internetExposed: true,
            tags: <String>['email', 'external-contact'],
          ),
          CyberAsset(
            id: 'frontdesk',
            name: 'Main Campus Reception',
            kind: AssetKind.facility,
            location: 'Main Campus / Lobby',
            criticality: 0.62,
            ownerRole: 'Facilities Security',
            tags: <String>['visitors', 'badge-access'],
          ),
          CyberAsset(
            id: 'supplier',
            name: 'Synthetic Billing Supplier',
            kind: AssetKind.supplier,
            location: 'External Supplier',
            criticality: 0.72,
            ownerRole: 'Vendor Risk',
            internetExposed: true,
            tags: <String>['third-party', 'billing'],
          ),
          CyberAsset(
            id: 'admin-laptop',
            name: 'Privileged Administrator Endpoint',
            kind: AssetKind.endpoint,
            location: 'Remote / managed',
            criticality: 0.92,
            ownerRole: 'Platform Administration',
            privileged: true,
            tags: <String>['endpoint', 'tier-0-admin'],
          ),
        ],
        humans: <HumanProfile>[
          HumanProfile(
            id: 'helpdesk-role',
            role: 'Help Desk Analyst Cohort',
            location: 'Main Campus',
            trainingScore: 0.68,
            workload: 0.84,
            externalContactRate: 0.88,
            mfaEnabled: true,
            passkeyEnabled: false,
          ),
          HumanProfile(
            id: 'admin-role',
            role: 'Privileged Platform Administrator Cohort',
            location: 'Remote / managed',
            trainingScore: 0.88,
            workload: 0.72,
            externalContactRate: 0.38,
            privileged: true,
            remoteWorker: true,
            mfaEnabled: true,
            passkeyEnabled: true,
          ),
          HumanProfile(
            id: 'frontdesk-role',
            role: 'Reception and Visitor Services Cohort',
            location: 'Main Campus / Lobby',
            trainingScore: 0.61,
            workload: 0.76,
            externalContactRate: 0.96,
            mfaEnabled: true,
            passkeyEnabled: false,
          ),
        ],
        controls: <SecurityControl>[
          SecurityControl(
            id: 'mfa-1',
            name: 'Workforce MFA',
            type: ControlType.mfa,
            effectiveness: 0.62,
            coverage: 0.96,
          ),
          SecurityControl(
            id: 'passkeys-1',
            name: 'Passkeys for privileged roles',
            type: ControlType.passkey,
            effectiveness: 0.91,
            coverage: 0.36,
            assetIds: <String>['idp', 'admin-laptop'],
          ),
          SecurityControl(
            id: 'vault-1',
            name: 'Managed secrets vault',
            type: ControlType.secretsVault,
            effectiveness: 0.82,
            coverage: 0.72,
            assetIds: <String>['secrets', 'ehr'],
          ),
          SecurityControl(
            id: 'email-1',
            name: 'Email authentication and filtering',
            type: ControlType.emailSecurity,
            effectiveness: 0.70,
            coverage: 0.94,
            assetIds: <String>['email'],
          ),
          SecurityControl(
            id: 'training-1',
            name: 'Role-based security training',
            type: ControlType.userTraining,
            effectiveness: 0.52,
            coverage: 0.88,
          ),
          SecurityControl(
            id: 'visitor-1',
            name: 'Visitor registration and escort',
            type: ControlType.visitorManagement,
            effectiveness: 0.58,
            coverage: 0.74,
            assetIds: <String>['frontdesk'],
          ),
          SecurityControl(
            id: 'edr-1',
            name: 'Endpoint detection and response',
            type: ControlType.endpointDetection,
            effectiveness: 0.78,
            coverage: 0.92,
            assetIds: <String>['admin-laptop'],
          ),
          SecurityControl(
            id: 'supplier-1',
            name: 'Supplier assurance review',
            type: ControlType.supplierAssurance,
            effectiveness: 0.46,
            coverage: 0.65,
            assetIds: <String>['supplier'],
          ),
        ],
        edges: <AttackSurfaceEdge>[
          AttackSurfaceEdge(
            fromId: 'email',
            toId: 'idp',
            vector: ThreatVector.phishing,
            baseLikelihood: 0.22,
            impactMultiplier: 0.86,
            label: 'Workforce identity recovery path',
          ),
          AttackSurfaceEdge(
            fromId: 'idp',
            toId: 'admin-laptop',
            vector: ThreatVector.credentialExposure,
            baseLikelihood: 0.16,
            impactMultiplier: 0.93,
            label: 'Privileged session access',
          ),
          AttackSurfaceEdge(
            fromId: 'admin-laptop',
            toId: 'secrets',
            vector: ThreatVector.credentialExposure,
            baseLikelihood: 0.18,
            impactMultiplier: 0.96,
            label: 'Administrative secret access',
          ),
          AttackSurfaceEdge(
            fromId: 'secrets',
            toId: 'ehr',
            vector: ThreatVector.dataExfiltration,
            baseLikelihood: 0.14,
            impactMultiplier: 1.0,
            label: 'Application credential trust',
          ),
          AttackSurfaceEdge(
            fromId: 'supplier',
            toId: 'ehr',
            vector: ThreatVector.supplyChain,
            baseLikelihood: 0.12,
            impactMultiplier: 0.84,
            label: 'Billing integration',
          ),
          AttackSurfaceEdge(
            fromId: 'frontdesk',
            toId: 'admin-laptop',
            vector: ThreatVector.physicalIntrusion,
            baseLikelihood: 0.08,
            impactMultiplier: 0.72,
            label: 'Shared campus access zone',
          ),
        ],
      );
}
