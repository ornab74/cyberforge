# CyberForge 3 Architecture

## 1. Design objective

CyberForge converts heterogeneous defensive observations into an authorized digital twin, simulates correlated failure pressure, and asks independent AI models to critique the result. It is not a vulnerability exploitation framework.

## 2. Runtime topology

```text
Flutter command center
        │ loopback HTTP + bearer session
        ▼
FastAPI local sidecar
  ├── authorization and prompt firewall
  ├── secret redactor
  ├── surface graph normalizer
  ├── Llama 3 per-surface micro-scanner
  ├── AEGIS-816 Monte Carlo + graph propagation engine
  ├── Gemma 4 private synthesis
  ├── optional redacted cloud council
  ├── AES-GCM provider/model vault
  └── optional ML-KEM hybrid recovery
```

The sidecar refuses non-loopback binding unless an explicit override is set. The Flutter application stores only a short-lived sidecar session token in platform secure storage.

## 3. Scanner pipeline

1. **Authorize.** Require a concrete ownership or authorization statement and bounded scope.
2. **Normalize.** Convert systems, people-role aggregates, sites, routes, APIs, cloud identities, suppliers, controls, and data classes into surfaces.
3. **Redact.** Remove credentials, API keys, passwords, tokens, and private-key material from model packets.
4. **Micro-scan.** When loaded, Llama 3 evaluates the highest-pressure individual surfaces locally.
5. **Graph propagate.** Bounded message passing estimates how weak trust links amplify pressure between surfaces.
6. **Simulate.** Seeded Monte Carlo worlds model common pressure, temporal windows, controls, impact, and uncertainty.
7. **Synthesize.** Gemma 4 can produce the private local narrative and control plan.
8. **Deliberate.** Optional GPT-5.6, Grok 4.5, Kimi K3, and Gemini calls receive only the redacted summary packet.
9. **Report.** Return risk dimensions, paths, hotspots, planning windows, affected-equivalent ranges, assumptions, controls, evidence requirements, and model disagreement.

## 4. Surface schema

A surface contains:

- stable ID and label;
- kind: identity, credential, endpoint, server, API, cloud, facility, route, vendor, human aggregate, data, network, or collective;
- optional named location and optional coordinates;
- criticality, exposure, control strength, human pressure, and telemetry confidence from 0 to 1;
- inventory count and defensive signal notes.

A link joins two surfaces and includes relationship type, trust, and control strength. Links represent dependencies and authorization pathways, not exploit instructions.

## 5. AEGIS-816 truth model

“Dyson Sphere Gamma” and “81,611,511 qubits” are interface metaphors for a quantum-inspired scheduler. The implementation uses deterministic pseudorandom seeds, NumPy vectorization, bounded graph propagation, and conventional CPU/GPU execution. The label appears in every report so a cinematic interface cannot be mistaken for physical hardware.

## 6. Model roles

| Model | Default role | Data boundary |
|---|---|---|
| Llama 3 Small Q3 | Surface micro-scanner | Local only |
| Gemma 4 E2B 4-bit | Private synthesis and report repair | Local only |
| GPT-5.6 | Deep independent defensive critique | Redacted packet only |
| Grok 4.5 on xAI | Independent frontier-model critique | Redacted packet only |
| Kimi K3 on DigitalOcean | Long-context systems critique | Redacted packet only |
| Gemini 3.6 Flash | Fast independent critique | Redacted packet only |
| Offline calibrator | Deterministic fallback | Local only |

Cloud failures are isolated. A failed provider does not prevent an offline report.

## 7. Output semantics

- **Risk** is relative planning pressure, not probability of a guaranteed incident.
- **Affected equivalent** is inventory losing trustworthy operation in a simulated world, not a malware count.
- **Timeline** is a recurring relative pressure window, not a reconstructed forensic timestamp.
- **Path** is trust amplification between surfaces, not an intrusion procedure.
- **Attribution** remains “not attributed” unless verified evidence is imported and reviewed by a human.
