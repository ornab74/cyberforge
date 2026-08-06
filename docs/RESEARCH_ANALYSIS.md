# CyberForge Research Analysis Layer

CyberForge's research endpoint adds three trust-oriented capabilities on top of
the existing AEGIS-816 defensive digital twin:

1. multi-resolution simulation with hotspot refinement;
2. bounded parameter sensitivity and Pareto control portfolios;
3. cryptographically verifiable reproducibility certificates and structured
   council disagreement audits.

It remains passive, local-first, authorization-gated, and defense-only. It does
not discover systems, make credentialed live queries, probe services, exploit
controls, generate offensive procedures, or attribute an actor.

## Endpoint

```text
POST /v1/research/analyze
```

The input uses the normal CyberForge scenario schema. An optional `research`
object controls bounded analysis settings:

```json
{
  "worlds": 12000,
  "seed": 3923929,
  "includeRemoteModels": false,
  "research": {
    "coarseWorlds": 1500,
    "sensitivityWorlds": 1200,
    "hotspotLimit": 3,
    "sensitivityDelta": 0.08,
    "debateRounds": 3
  }
}
```

All world counts are bounded by the sidecar settings. Sensitivity analysis is
restricted to the highest-ranked surfaces and a fixed allow-list of planning
parameters.

## Multi-resolution simulation

The engine performs a fast seeded whole-graph pass to identify hotspot surfaces,
then runs the requested deeper pass on the same normalized scenario and seed.
The response includes both outputs and their difference.

This is a computational prioritization strategy. A coarse-to-deep difference is
not evidence that either value is a measured probability.

## Sensitivity analysis

For each selected hotspot, CyberForge perturbs:

- `controlStrength`
- `exposure`
- `telemetryConfidence`
- `humanPressure`
- `criticality`

The same seed and world count are reused for each low/high experiment. The
reported influence is the change in modeled overall pressure per unit of bounded
parameter movement.

Sensitivity indicates model responsiveness under a counterfactual. It does not
prove real-world causality and should be interpreted alongside evidence quality,
parameter provenance, and domain review.

## Pareto control frontier

CyberForge generates a bounded set of defensive control candidates for the
selected hotspots. Each candidate has:

- a modeled parameter change;
- optional user-provided implementation cost;
- estimated residual pressure;
- estimated pressure reduction;
- reduction-per-cost efficiency.

The response retains non-dominated candidates: no retained option is both more
expensive and less effective than another modeled option. Costs are planning
inputs, not market estimates. Pressure reduction remains a simulation output.

Custom cost keys use this form:

```json
{
  "controlCosts": {
    "remote-access:controlStrength": 4.0,
    "identity-workforce:telemetryConfidence": 1.5
  }
}
```

## Council disagreement audit

The endpoint runs bounded council rounds using consensus, forced-dissent, and
auditor metadata. Local models run first when loaded; cloud critics remain opt-in
and receive only the redacted packet.

CyberForge calculates disagreement from priority-vector diversity and uncertainty
spread. It also records when a model changes its ranked vectors between rounds.
These are deterministic audit metrics over model opinions, not correctness scores.

## Reproducibility certificate

Each completed analysis receives a locally signed certificate containing:

- redacted packet digest;
- graph digest;
- stable result digest;
- seed and world count;
- CyberForge code version;
- pinned local-model hashes;
- whether remote models participated;
- redaction count;
- truth label.

The sidecar generates an Ed25519 key under its local data directory and stores it
with restrictive file permissions when supported. The private key is never added
to the report. The certificate includes the public key, public-key fingerprint,
signature, and run fingerprint.

Verify a certificate with:

```text
POST /v1/research/verify-certificate
```

```json
{
  "certificate": { "...": "certificate returned by /analyze" }
}
```

A valid signature means the certificate core and fingerprint have not changed
since they were signed by that CyberForge installation. It does not independently
validate scenario assumptions, model calibration, imported evidence, or the
correctness of defensive recommendations.

## Truth labels

The research response explicitly labels:

- seeded counterfactual simulation outputs;
- counterfactual sensitivity;
- counterfactual control estimates;
- model opinions and deterministic disagreement metrics;
- reproducibility metadata and cryptographic attestation.

None of these labels should be converted into a claim that compromise occurred,
that a specific actor exists, or that a modeled pressure score is an incident
probability.
