# CyberForge Memory Governance and Council Protocol V2

This layer advances CyberForge from encrypted persistence into governed,
verifiable institutional memory and genuinely role-separated model review.

## Memory integrity verification

```text
GET /v1/memory/integrity
Authorization: Bearer <unlocked-vault-session>
```

The verifier checks:

- SQLite `PRAGMA integrity_check`;
- foreign-key consistency;
- AES-256-GCM authentication for every active encrypted record;
- the canonical digest stored with each record;
- every encrypted audit event;
- continuity of the hash-linked audit chain;
- agreement between encrypted audit fields and bounded routing columns;
- restrictive database file permissions when supported.

A healthy result means the local structures and authenticated ciphertext are
internally consistent. It does not validate that operator inputs, imported
evidence, simulations, or model opinions are factually correct.

## Retention planning and legal holds

Retention is always a two-stage operation.

Dry run:

```text
POST /v1/memory/retention/plan
```

Example body:

```json
{
  "policy_days": {
    "health": 7,
    "council-opinion": 365,
    "research-run": 730,
    "certificate": 3650
  }
}
```

The response lists deletion candidates and separately lists held records. Holds
can be expressed through tags such as `legal-hold`, `retention-hold`,
`preserve`, or `do-not-delete`, or through protected metadata flags.

Applying deletion requires the exact confirmation phrase:

```text
APPLY CYBERFORGE RETENTION
```

```text
POST /v1/memory/retention/apply
```

Deleted encrypted records are soft-deleted locally, receive encrypted audit
events, and are queued for removal from Weaviate. A malformed future hold date is
treated conservatively as a hold.

## Provenance graph

```text
GET /v1/memory/provenance/{record_id}?max_depth=3&max_nodes=128
```

CyberForge builds a bounded graph from explicit metadata references such as:

- `sourceRecordIds`;
- `parentRecordId`;
- `derivedFrom`;
- `provenance`;
- `relatedRecordIds`.

Edges are assertions stored in encrypted metadata. Missing edges do not prove
that two records are independent.

## Provenance-preserving compaction

```text
POST /v1/memory/compact
```

A compaction record contains source identifiers, authenticated source digests,
record types, tags, summaries, and timestamps. It does not delete or replace the
source records. The generated compaction record carries a retention hold by
default because it acts as a navigational and evidentiary index.

This supports long-running CyberForge installations without converting memory
maintenance into irreversible summarization.

## Full Weaviate rebuild

Weaviate remains a disposable redacted search accelerator. Every active
projection can be regenerated from encrypted SQLite.

```text
POST /v1/memory/weaviate/rebuild
```

The exact confirmation phrase is:

```text
REBUILD CYBERFORGE WEAVIATE
```

The operation queues every active record for projection regeneration and then
runs the normal bounded synchronization path. Full payloads and vault material
never enter Weaviate.

## Role-separated council protocol

The earlier research layer carried role metadata inside the analyzed packet.
That was useful for auditing, but it did not guarantee that provider system
prompts differed by round.

Council Protocol V2 introduces three trusted controller roles:

1. **Consensus Architect** — builds the strongest shared interpretation while
   retaining uncertainty and falsification evidence.
2. **Forced-Dissent Critic** — steelmans a materially different interpretation,
   challenges correlated assumptions, and proposes alternative defensive
   priorities.
3. **Reproducibility and Evidence Auditor** — audits provenance, truth labels,
   ownership, validation, rollback, sensitivity claims, and evidence gaps.

Role instructions are injected as trusted controller system text. Scenario,
simulation, evidence, and prior-round material remain untrusted redacted data.
A serialized compatibility bridge isolates the module-level provider prompt until
all provider adapters accept explicit controller instructions directly.

## Bounded prior-round context

Each round can see a bounded summary of at most two prior rounds. The context
includes successful model summaries, vectors, controls, uncertainty,
assumptions, and evidence needs. It excludes raw hidden reasoning and truncates
large material.

## Deterministic council audit metrics

Each round includes:

- evidence-quality estimates based on structured assumptions, evidence needs,
  focused vectors, concrete controls, and stated uncertainty;
- vector vote distributions;
- pairwise contradiction scores;
- maximum contradiction;
- stable council digests that exclude latency and timestamps.

These are deterministic metrics over model outputs. They are not model accuracy,
calibration, or correctness scores.

## Stable reproducibility certificates

Research endpoint certificates now digest a stable debate view. Request latency
and other operational timing noise do not change the debate digest. Role IDs,
missions, stable opinions, consensus results, contradiction metrics, and evidence
quality remain part of the signed result boundary.

## Security boundary

This layer does not claim to protect cleartext from a process that is already
fully compromised while the vault is unlocked. It protects stored records at
rest, detects ciphertext and audit-chain tampering, limits destructive retention,
keeps vector infrastructure reconstructible, and makes model-role boundaries
explicit and testable.
