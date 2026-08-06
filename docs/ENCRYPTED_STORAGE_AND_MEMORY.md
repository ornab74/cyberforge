# Encrypted Storage and Advanced Weaviate Memory

CyberForge uses a two-layer memory architecture:

1. **Encrypted SQLite is the authoritative system of record.**
2. **Weaviate is a disposable, redacted search projection.**

This separation prevents the vector database from becoming a second plaintext
repository of scenarios, reports, council transcripts, certificates, or imported
evidence.

## Encrypted SQLite

The SQLite database stores every durable CyberForge artifact as an independently
authenticated AES-256-GCM record. The encryption master key is random and stored
inside the existing CyberForge vault. The vault therefore must be unlocked before
records can be written, read, searched, or deleted.

The database contains only:

- record identifiers and bounded routing fields;
- timestamps, truth labels, validation status, and digests;
- AES-GCM nonce and ciphertext;
- HMAC-SHA-256 blind-search tokens;
- a durable Weaviate synchronization queue;
- an encrypted, hash-linked audit chain.

Titles, summaries, tags, metadata, complete scenario packets, full simulation
results, council debate outputs, and certificates remain inside encrypted record
payloads.

Blind-search tokens allow deterministic lexical candidate retrieval without
placing plaintext terms in the database. Search results are decrypted only after
the caller presents a valid short-lived vault bearer session.

## Automatic research-run persistence

`POST /v1/research/analyze` remains usable without a vault session. Such a run is
ephemeral.

When the request includes a valid bearer session, CyberForge stores one encrypted
`research-run` record containing:

- the authorized scenario packet;
- coarse and deep simulation results;
- sensitivity experiments;
- Pareto control options;
- council debate rounds and disagreement metrics;
- the signed reproducibility certificate.

The response includes a `persistence` object with the encrypted record identifier
and authenticated digest.

## Weaviate boundary

Weaviate receives only a redacted and reconstructible projection:

- encrypted SQLite record ID;
- record type;
- redacted title and summary;
- truth and validation labels;
- one-way scope hash;
- record digest;
- redacted tags and bounded metadata;
- timestamps;
- a flag stating that the object is a redacted projection.

It never receives the complete encrypted payload or vault keys.

Deleting the Weaviate collection does not destroy CyberForge history. Running the
synchronization endpoint reconstructs the index from encrypted SQLite.

## Weaviate modes

`CYBERFORGE_WEAVIATE_MODE` accepts:

- `auto`: try remote Weaviate, then Embedded Weaviate, then continue with SQLite;
- `remote`: require the configured remote service;
- `embedded`: launch the pinned native Weaviate binary through the Python client;
- `off`: use encrypted SQLite retrieval only.

As in Humoid Agent TUI, initialization performs three readiness gates:

1. server liveness;
2. collection-schema availability;
3. insert, fetch, hybrid-search, and delete sentinel round-trip.

A failed Weaviate service never prevents encrypted SQLite from accepting records.
The durable synchronization queue records failed projections for later replay.

## Named vectors and hybrid retrieval

The collection has two self-provided named vectors:

- `content`: redacted title, summary, truth labels, tags, and metadata;
- `topology`: record type, topology-oriented tags, and structural metadata.

CyberForge currently uses a deterministic local feature-hashing vector. It needs
no external embedding API and sends no content off-device. A later local embedding
model can replace this vector producer without changing the encrypted SQLite
schema.

Search combines:

1. encrypted SQLite blind lexical retrieval;
2. Weaviate hybrid BM25/vector retrieval;
3. reciprocal-rank fusion across providers;
4. temporal-neighbor expansion from the authoritative SQLite timeline;
5. maximal marginal relevance to reduce repetitive results.

The final context packet contains metadata and summaries, not full record payloads.
The caller must fetch a specific encrypted record explicitly to obtain its full
contents.

## APIs

All storage routes require an unlocked-vault bearer session.

```text
GET    /v1/storage/status
POST   /v1/storage/records
GET    /v1/storage/records
GET    /v1/storage/records/{record_id}
DELETE /v1/storage/records/{record_id}
POST   /v1/storage/search
POST   /v1/storage/context
POST   /v1/storage/sync-weaviate
```

## Installation

Core encrypted SQLite support uses the standard-library SQLite driver and existing
CyberForge cryptography dependencies.

Install optional Weaviate support with:

```bash
python -m pip install -r sidecar/requirements-memory.txt
```

The Docker image includes the Weaviate client. The repository Compose file starts
a loopback-only Weaviate 1.37.0 service with persistent storage, disabled telemetry,
a health check, and no host-wide network exposure.

For a production multi-user or remote deployment, disable anonymous Weaviate
access and configure API-key or OIDC authentication plus TLS. The provided Compose
configuration is intended for a single local CyberForge installation bound to
loopback.

## Security properties and limits

- AES-GCM authenticates each record independently.
- HKDF separates record encryption, blind indexing, and audit-chain keys.
- The storage master key is wrapped by the existing Argon2id/AES-GCM vault.
- Database file and parent directories use restrictive permissions when supported.
- Secret redaction occurs before a projection enters Weaviate.
- Full-text SQL search is intentionally not used because it would expose plaintext.
- File names, record types, timestamps, truth labels, and validation status remain
  visible as database routing metadata.
- A process running as the unlocked CyberForge user can request record decryption;
  this design protects data at rest, not a fully compromised live process.
- The deterministic feature-hash vector is private and local, but it is not a
  semantic embedding model.
