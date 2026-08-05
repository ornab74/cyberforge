# CyberForge Architecture

## 1. Trust boundary

CyberForge begins with authorization rather than model inference. `AuthorizationPolicy` validates the scenario before any simulation or provider call. Version 0.1 permits only synthetic digital twins with a specific authorization statement and a bounded horizon.

## 2. Domain layer

`lib/src/domain/models.dart` defines immutable data structures for:

- cyber and physical assets
- security controls
- synthetic human-role cohorts
- directed attack-surface relationships
- findings, telemetry, and reports

The same schema is used by the UI, CLI, tests, and model council.

## 3. Attack-surface graph

`AttackSurfaceGraph` builds an adjacency map from the scenario. It estimates reachable assets and a criticality-weighted blast radius without probing a network. Edges are declarative planning relationships, not executable attack steps.

## 4. Risk engine

`RiskEngine` combines:

- vector-specific priors
- internet exposure
- privilege
- criticality
- graph blast radius
- human training and workload
- external contact rate
- remote-work exposure
- MFA and passkey coverage
- control effectiveness and coverage

A logistic transform converts the combined score into a bounded probability.

## 5. Gamma compute fabric

`GammaComputeFabric` is conventional software. It performs seeded Monte Carlo sampling and reports a coherence-like agreement metric. The 3,923,929 register and Dyson-sphere language are simulation labels and scaling metaphors—not claims of access to physical qubits or extraterrestrial infrastructure.

The seed makes scenario comparisons reproducible. Multiple worlds let defenders compare distributions instead of relying on one deterministic score.

## 6. Simulation engine

For each world, the engine evaluates asset and human-vector combinations, applies temporal multipliers, samples outcomes, and aggregates:

- finding probability
- impact
- confidence
- likely time window
- location hotspots
- defensive recommendations

No packets are sent, no ports are scanned, and no exploit is executed.

## 7. Model council

The council receives a compact report packet—not raw secret material. Before any provider call:

1. `SecretRedactor` removes common token, key, password, bearer-token, and private-key patterns.
2. `PromptFirewall` blocks operational offensive requests and marks sensitive defensive topics for constrained review.
3. Each adapter receives the same defensive JSON schema and hard boundaries.
4. Failed or unconfigured providers degrade gracefully.
5. Consensus is calculated from overlapping priority vectors, while disagreement remains visible.

The offline adapter is always available. Remote adapters are optional.

## 8. Provider adapters

- OpenAI Responses API adapter
- xAI Responses API adapter
- Google Gemini `generateContent` adapter
- Local OpenAI-compatible Gemma adapter
- Offline policy ensemble

Adapters implement one interface so providers can be replaced without changing the simulation core.

## 9. UI

The Flutter UI contains four workspaces:

- Command overview
- Attack-surface digital twin
- Multi-model council
- Authorization and safety boundary

The UI intentionally exposes uncertainty, assumptions, provider failures, and the simulated nature of Gamma telemetry.

## 10. Extension points

Safe future extensions include:

- policy-as-code import
- SBOM and supplier graph ingestion
- privacy-preserving aggregate identity telemetry
- control-cost optimization
- scenario diffing
- signed report exports
- local vector memory for past defensive findings
- calibrated Bayesian updating from validated incidents
- detection coverage mapping to MITRE ATT&CK techniques without operational payload generation
