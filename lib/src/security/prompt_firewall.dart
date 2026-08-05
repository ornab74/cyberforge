enum PromptRisk { allowed, review, blocked }

final class PromptFirewallDecision {
  const PromptFirewallDecision({
    required this.risk,
    required this.reason,
  });

  final PromptRisk risk;
  final String reason;

  bool get allowed => risk != PromptRisk.blocked;
}

final class PromptFirewall {
  const PromptFirewall();

  static final List<RegExp> _blocked = <RegExp>[
    RegExp(r'steal\s+(?:a\s+)?password', caseSensitive: false),
    RegExp(r'bypass\s+(?:mfa|2fa|authentication)', caseSensitive: false),
    RegExp(r'write\s+(?:a\s+)?phishing\s+(?:email|page|kit)', caseSensitive: false),
    RegExp(r'deploy\s+(?:ransomware|malware)', caseSensitive: false),
    RegExp(r'break\s+into\s+(?:the\s+)?(?:building|office|server)', caseSensitive: false),
    RegExp(r'exfiltrate\s+(?:data|secrets|credentials)', caseSensitive: false),
    RegExp(r'generate\s+(?:an\s+)?exploit\s+(?:payload|chain)', caseSensitive: false),
  ];

  static final List<RegExp> _review = <RegExp>[
    RegExp(r'penetration\s+test', caseSensitive: false),
    RegExp(r'credential\s+(?:attack|spray|stuffing)', caseSensitive: false),
    RegExp(r'physical\s+security', caseSensitive: false),
    RegExp(r'red\s+team', caseSensitive: false),
  ];

  PromptFirewallDecision inspect(String text) {
    for (final pattern in _blocked) {
      if (pattern.hasMatch(text)) {
        return const PromptFirewallDecision(
          risk: PromptRisk.blocked,
          reason:
              'Request asks for operational attack instructions. CyberForge only supports prediction, detection, mitigation, and authorized simulation.',
        );
      }
    }
    for (final pattern in _review) {
      if (pattern.hasMatch(text)) {
        return const PromptFirewallDecision(
          risk: PromptRisk.review,
          reason:
              'Sensitive defensive topic detected. Keep output non-operational, synthetic, and focused on controls and detection.',
        );
      }
    }
    return const PromptFirewallDecision(
      risk: PromptRisk.allowed,
      reason: 'Request is within the defense-first simulation policy.',
    );
  }
}
