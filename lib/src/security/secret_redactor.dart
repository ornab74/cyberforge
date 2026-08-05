final class RedactionResult {
  const RedactionResult({required this.text, required this.redactionCount});

  final String text;
  final int redactionCount;
}

final class SecretRedactor {
  const SecretRedactor();

  static final List<RegExp> _patterns = <RegExp>[
    RegExp(
      r'''(?:(?:api[_-]?key)|secret|token|password|passwd)\s*[:=]\s*["']?[^\s,"']{8,}''',
      caseSensitive: false,
    ),
    RegExp(r'bearer\s+[a-z0-9._\-]{12,}', caseSensitive: false),
    RegExp(r'AKIA[0-9A-Z]{16}'),
    RegExp(
      r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    ),
    RegExp(r'\b(?:sk|xai|AIza)[-_A-Za-z0-9]{16,}\b'),
  ];

  RedactionResult redact(String input) {
    var output = input;
    var count = 0;
    for (final pattern in _patterns) {
      output = output.replaceAllMapped(pattern, (match) {
        count += 1;
        final whole = match.group(0) ?? '';
        final separator = whole.indexOf(RegExp(r'[:=]'));
        if (separator >= 0) {
          return '${whole.substring(0, separator + 1)} [REDACTED]';
        }
        return '[REDACTED_SECRET]';
      });
    }
    return RedactionResult(text: output, redactionCount: count);
  }
}
