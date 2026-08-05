# Validation Report

Build validation performed on 2026-08-04 against the standalone CyberForge 3 source tree.

## Passed

- Python 3.13 bytecode compilation for every sidecar module.
- 11 automated tests covering AES-GCM byte and streaming round trips, guardrails, recursive secret redaction, deterministic simulation, SIMCOM attribution refusal, provider-schema allow-listing, requested council membership, offline fallback, and vault data-key rotation.
- FastAPI smoke checks for health, default scenario, authorized scan, and SIMCOM scan endpoints.
- CLI checks for JSON scan output, BOOTCOM, and command-local SIMCOM options.
- Default and advanced scenario JSON parsing.
- Scanner output checks for findings, trust paths, authorization state, impact ranges, and the no-attribution boundary.
- Static Dart delimiter checks across application and test sources.
- Repository scans for committed provider-key patterns and prohibited real-organization references.

## Environment-limited checks

Flutter and Dart SDK executables were not installed in the build container, so `flutter analyze` and `flutter test` were not run locally. The GitHub Actions workflow runs both when the repository is published.

The large Gemma and Llama runtimes were intentionally not downloaded into the source package. Their pinned profiles, hash verification, encrypted installation path, runtime adapters, failure isolation, and controls are present. End-to-end inference requires installing the platform-compatible local-model dependencies and downloading the verified model files through the vault-authorized installer.

ML-KEM recovery is capability-gated and requires `liboqs-python` plus a compatible host `liboqs` installation. AES-256-GCM remains available without that optional dependency.
