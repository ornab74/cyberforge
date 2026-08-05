# Contributing

1. Keep every feature defense-first and synthetic by default.
2. Add tests for risk, redaction, authorization, and provider parsing changes.
3. Do not add live scanning, exploit execution, credential collection, or physical-intrusion guidance.
4. Preserve uncertainty and assumptions in every report.
5. Run `flutter analyze` and `flutter test` before opening a pull request.
6. Explain the safety impact of model or prompt changes in the pull request description.
