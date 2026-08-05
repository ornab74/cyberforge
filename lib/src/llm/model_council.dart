import 'dart:convert';

import '../domain/models.dart';
import '../security/prompt_firewall.dart';
import '../security/secret_redactor.dart';
import 'llm_adapter.dart';

final class CouncilReport {
  const CouncilReport({
    required this.opinions,
    required this.consensusSummary,
    required this.consensusVectors,
    required this.consensusControls,
    required this.disagreement,
    required this.redactionCount,
  });

  final List<ModelOpinion> opinions;
  final String consensusSummary;
  final List<ThreatVector> consensusVectors;
  final List<String> consensusControls;
  final double disagreement;
  final int redactionCount;

  Map<String, Object?> toJson() => <String, Object?>{
        'opinions': opinions.map((e) => e.toJson()).toList(growable: false),
        'consensusSummary': consensusSummary,
        'consensusVectors': consensusVectors.map((e) => e.name).toList(),
        'consensusControls': consensusControls,
        'disagreement': disagreement,
        'redactionCount': redactionCount,
      };
}

final class ModelCouncil {
  const ModelCouncil({
    required this.adapters,
    this.redactor = const SecretRedactor(),
    this.firewall = const PromptFirewall(),
  });

  final List<LlmAdapter> adapters;
  final SecretRedactor redactor;
  final PromptFirewall firewall;

  Future<CouncilReport> deliberate({
    required SimulationScenario scenario,
    required SimulationReport report,
  }) async {
    final rawPrompt = _buildPrompt(scenario, report);
    final firewallDecision = firewall.inspect(rawPrompt);
    if (!firewallDecision.allowed) {
      throw StateError(firewallDecision.reason);
    }
    final redacted = redactor.redact(rawPrompt);
    final configured = adapters.where((adapter) => adapter.configured).toList();
    if (configured.isEmpty) {
      throw StateError('No model adapters are configured.');
    }
    final opinions = await Future.wait(
      configured.map(
        (adapter) => adapter.analyze(
          scenario: scenario,
          report: report,
          policyPrompt: redacted.text,
        ),
      ),
    );
    final successful = opinions.where((opinion) => opinion.succeeded).toList();
    final vectorVotes = <ThreatVector, double>{};
    final controlVotes = <String, double>{};
    for (final opinion in successful) {
      final weight = (1 - opinion.uncertainty).clamp(0.05, 1.0).toDouble();
      for (final vector in opinion.priorityVectors) {
        vectorVotes[vector] = (vectorVotes[vector] ?? 0) + weight;
      }
      for (final control in opinion.recommendedControls) {
        final normalized = control.trim();
        if (normalized.isNotEmpty) {
          controlVotes[normalized] = (controlVotes[normalized] ?? 0) + weight;
        }
      }
    }
    final vectors = vectorVotes.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final controls = controlVotes.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final disagreement = _disagreement(successful);
    final providerNames = successful.map((opinion) => opinion.model).join(', ');
    final leadingVectors = vectors.take(3).map((entry) => entry.key.name).join(', ');
    final summary = successful.isEmpty
        ? 'All configured model calls failed. Use the offline simulation findings and inspect adapter errors.'
        : 'Council consensus from $providerNames prioritizes $leadingVectors. Model disagreement is ${(disagreement * 100).toStringAsFixed(0)}%; validate high-impact decisions with human review and observable telemetry.';
    return CouncilReport(
      opinions: opinions,
      consensusSummary: summary,
      consensusVectors: vectors.take(5).map((entry) => entry.key).toList(growable: false),
      consensusControls:
          controls.take(10).map((entry) => entry.key).toList(growable: false),
      disagreement: disagreement,
      redactionCount: redacted.redactionCount,
    );
  }

  String _buildPrompt(SimulationScenario scenario, SimulationReport report) {
    final compactFindings = report.findings.take(12).map(
          (finding) => <String, Object?>{
            'title': finding.title,
            'vector': finding.vector.name,
            'severity': finding.severity.name,
            'probability': finding.probability,
            'impact': finding.impact,
            'confidence': finding.confidence,
            'location': finding.location,
            'likelyWindow': finding.likelyWindow,
          },
        );
    final packet = <String, Object?>{
      'scenario': <String, Object?>{
        'name': scenario.name,
        'description': scenario.description,
        'authorizationStatement': scenario.authorizationStatement,
        'synthetic': scenario.synthetic,
        'timeHorizonDays': scenario.timeHorizonDays,
        'assetCount': scenario.assets.length,
        'humanProfileCount': scenario.humans.length,
        'controlCount': scenario.controls.length,
      },
      'simulation': <String, Object?>{
        'overallRisk': report.overallRisk,
        'findings': compactFindings.toList(growable: false),
        'locationRisk': report.locationRisk,
        'timelineRisk': report.timelineRisk.map(
          (hour, risk) => MapEntry(hour.toString(), risk),
        ),
      },
    };
    return '''
You are one member of the CyberForge blue-team model council.

Purpose: predict defensive risk and recommend controls for an authorized synthetic security digital twin.

Hard boundaries:
- Do not provide exploit payloads, malware, phishing copy, credential theft instructions, evasion, or physical intrusion procedures.
- Do not infer or invent real passwords, keys, personal identities, or targetable vulnerabilities.
- Do not recommend attacking a live target.
- Focus on probability, uncertainty, detection, prevention, resilience, and safe validation.
- Separate observed scenario facts from assumptions.

Return exactly one JSON object with this schema:
{
  "summary": "defensive assessment under 180 words",
  "priorityVectors": ["one or more ThreatVector enum names"],
  "recommendedControls": ["specific defensive improvements"],
  "uncertainty": 0.0,
  "assumptions": ["explicit assumptions"]
}

Allowed ThreatVector names:
${ThreatVector.values.map((value) => value.name).join(', ')}

Authorized scenario packet:
${const JsonEncoder.withIndent('  ').convert(packet)}
''';
  }

  double _disagreement(List<ModelOpinion> opinions) {
    if (opinions.length < 2) return 0;
    final allVectors = opinions.expand((opinion) => opinion.priorityVectors).toSet();
    if (allVectors.isEmpty) return 1;
    var pairCount = 0;
    var similarityTotal = 0.0;
    for (var i = 0; i < opinions.length; i += 1) {
      for (var j = i + 1; j < opinions.length; j += 1) {
        final a = opinions[i].priorityVectors.toSet();
        final b = opinions[j].priorityVectors.toSet();
        final union = a.union(b);
        final intersection = a.intersection(b);
        similarityTotal += union.isEmpty ? 1 : intersection.length / union.length;
        pairCount += 1;
      }
    }
    return (1 - similarityTotal / pairCount).clamp(0.0, 1.0).toDouble();
  }
}
