# CyberForge Threat Model

## Protected assets

- provider API keys;
- local-model encryption key;
- imported defensive observations;
- scenario reports and digests;
- vault root, index, and data keys;
- post-quantum recovery material;
- authorization statements and scope metadata.

## Primary adversaries

1. Malware or another local user reading application files.
2. A compromised cloud model attempting prompt injection or secret extraction.
3. A malicious scenario file embedding instructions or secrets.
4. Network listeners attempting to reach the sidecar.
5. Accidental operator misuse of a defensive simulator as an offensive assistant.
6. Dependency or model-file substitution.

## Controls

- loopback-only sidecar by default;
- explicit remote-bind override;
- request-size limits and bounded surface/world counts;
- authorization gate and blocked-intent patterns;
- recursive secret redaction;
- provider secrets separated from prompt packets;
- AES-GCM record vault and encrypted model storage;
- pinned model hashes before and after decryption;
- short-lived bearer sessions in platform secure storage;
- model/provider failure isolation;
- explicit attribution and simulation truth labels;
- optional hybrid post-quantum recovery;
- container profile with dropped capabilities and read-only root filesystem.

## Residual risks

- A fully compromised endpoint can capture data after unlock.
- Cloud providers receive redacted content but still learn that a request occurred.
- Regex redaction cannot identify every possible secret format.
- Model output may be wrong or overconfident.
- Numerical priors encode assumptions and require human calibration.
- Model provenance remains dependent on the pinned artifact source and build chain.

## Operational guidance

Run CyberForge on an encrypted, patched device. Keep cloud participation disabled for sensitive simulations. Use synthetic identifiers. Import only the minimum telemetry needed. Review every report as a hypothesis and validate controls through safe, authorized evidence collection.
