import '../domain/models.dart';

final class AuthorizationDecision {
  const AuthorizationDecision({
    required this.allowed,
    required this.reasons,
  });

  final bool allowed;
  final List<String> reasons;
}

final class AuthorizationPolicy {
  const AuthorizationPolicy();

  AuthorizationDecision evaluate(SimulationScenario scenario) {
    final reasons = <String>[];
    if (scenario.authorizationStatement.trim().length < 20) {
      reasons.add('A specific authorization statement is required.');
    }
    if (!scenario.synthetic) {
      reasons.add(
        'This build only executes synthetic digital-twin scenarios.',
      );
    }
    if (scenario.assets.isEmpty) {
      reasons.add('At least one modeled asset is required.');
    }
    if (scenario.timeHorizonDays < 1 || scenario.timeHorizonDays > 365) {
      reasons.add('The simulation horizon must be between 1 and 365 days.');
    }
    return AuthorizationDecision(allowed: reasons.isEmpty, reasons: reasons);
  }
}
