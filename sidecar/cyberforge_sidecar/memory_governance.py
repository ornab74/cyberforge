from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from hashlib import sha3_256
from typing import Any, Iterable
import hmac
import json
import os

from .crypto import CryptoError, aes_gcm_decrypt
from .storage import STORE_FORMAT, STORAGE, EncryptedSQLiteStore, StorageError, StoredRecord, utcnow


RETENTION_CONFIRMATION = "APPLY CYBERFORGE RETENTION"
REBUILD_CONFIRMATION = "REBUILD CYBERFORGE WEAVIATE"

DEFAULT_RETENTION_DAYS: dict[str, int] = {
    "research-run": 730,
    "scenario": 730,
    "infrastructure-map": 730,
    "report": 730,
    "certificate": 3650,
    "evidence": 1095,
    "council-opinion": 365,
    "memory-compaction": 1095,
    "health": 7,
    "default": 365,
}

HOLD_TAGS = {
    "legal-hold",
    "retention-hold",
    "preserve",
    "do-not-delete",
    "incident-record",
}

REFERENCE_KEYS = {
    "sourceRecordIds",
    "source_record_ids",
    "sourceIds",
    "source_ids",
    "parentRecordId",
    "parent_record_id",
    "derivedFrom",
    "derived_from",
    "provenance",
    "relatedRecordIds",
    "related_record_ids",
}


class GovernanceError(StorageError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GovernanceError(f"Invalid stored timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _retention_policy(overrides: dict[str, int] | None = None) -> dict[str, int]:
    policy = dict(DEFAULT_RETENTION_DAYS)
    environment_default = os.environ.get("CYBERFORGE_RETENTION_DEFAULT_DAYS")
    if environment_default:
        policy["default"] = max(1, min(36500, int(environment_default)))
    for record_type, days in (overrides or {}).items():
        normalized = str(record_type).strip()[:96]
        if not normalized:
            continue
        policy[normalized] = max(1, min(36500, int(days)))
    return policy


def _held(record: StoredRecord) -> tuple[bool, str | None]:
    tags = {tag.strip().lower() for tag in record.tags}
    matching = sorted(tags & HOLD_TAGS)
    if matching:
        return True, f"hold tag: {matching[0]}"
    metadata = record.metadata
    for key in ("retentionHold", "legalHold", "preserve", "doNotDelete"):
        if metadata.get(key) is True:
            return True, f"metadata hold: {key}"
    hold_until = metadata.get("holdUntil")
    if isinstance(hold_until, str) and hold_until:
        try:
            if _parse_time(hold_until) > datetime.now(timezone.utc):
                return True, f"hold until {hold_until}"
        except GovernanceError:
            return True, "malformed holdUntil treated as a hold"
    return False, None


def _record_view(record: StoredRecord) -> dict[str, Any]:
    return {
        "recordId": record.record_id,
        "recordType": record.record_type,
        "title": record.title,
        "summary": record.summary,
        "tags": list(record.tags),
        "truthLabel": record.truth_label,
        "validationStatus": record.validation_status,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
        "digest": record.digest,
        "scopeHash": record.scope_hash,
        "metadata": record.metadata,
    }


def _all_active_records(token: str, store: EncryptedSQLiteStore) -> list[StoredRecord]:
    store.initialize()
    with store._connect() as database:  # intentional internal audit path
        rows = database.execute(
            "SELECT * FROM records WHERE deleted = 0 ORDER BY created_at ASC"
        ).fetchall()
    return [store._decode_row(token, row) for row in rows]


def verify_integrity(
    token: str,
    *,
    store: EncryptedSQLiteStore | None = None,
) -> dict[str, Any]:
    """Verify SQLite, record AEAD/digests, and the encrypted hash-linked audit chain."""

    store = store or STORAGE.sqlite
    store.initialize()
    _, _, audit_key = store._keys(token)

    record_failures: list[dict[str, str]] = []
    audit_failures: list[dict[str, str]] = []
    with store._connect() as database:
        sqlite_integrity = str(database.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_rows = database.execute("PRAGMA foreign_key_check").fetchall()
        record_rows = database.execute(
            "SELECT * FROM records WHERE deleted = 0 ORDER BY created_at ASC"
        ).fetchall()
        audit_rows = database.execute(
            "SELECT * FROM audit_chain ORDER BY sequence ASC"
        ).fetchall()

    verified_records = 0
    for row in record_rows:
        try:
            store._decode_row(token, row)
            verified_records += 1
        except Exception as exc:
            record_failures.append(
                {
                    "recordId": str(row["record_id"]),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    previous_hash = "0" * 64
    verified_audit_events = 0
    for row in audit_rows:
        event_hash = str(row["event_hash"])
        try:
            if not hmac.compare_digest(str(row["previous_hash"]), previous_hash):
                raise GovernanceError("previous hash does not match the verified chain head")
            aad = f"{STORE_FORMAT}:audit:{event_hash}".encode("utf-8")
            clear = aes_gcm_decrypt(
                {"nonce": str(row["nonce"]), "ciphertext": str(row["ciphertext"])},
                audit_key,
                aad,
            )
            event = json.loads(clear.decode("utf-8"))
            calculated = sha3_256(previous_hash.encode("ascii") + _canonical(event)).hexdigest()
            if not hmac.compare_digest(calculated, event_hash):
                raise GovernanceError("event hash does not authenticate the decrypted event")
            if str(event.get("operation")) != str(row["operation"]):
                raise GovernanceError("encrypted operation differs from the routing column")
            if str(event.get("recordId")) != str(row["record_id"]):
                raise GovernanceError("encrypted record identifier differs from the routing column")
            verified_audit_events += 1
            previous_hash = event_hash
        except (CryptoError, UnicodeDecodeError, json.JSONDecodeError, GovernanceError) as exc:
            audit_failures.append(
                {
                    "sequence": str(row["sequence"]),
                    "recordId": str(row["record_id"]),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            break

    mode = store.path.stat().st_mode & 0o777 if store.path.exists() else None
    healthy = (
        sqlite_integrity.lower() == "ok"
        and not foreign_key_rows
        and not record_failures
        and not audit_failures
        and verified_audit_events == len(audit_rows)
    )
    return {
        "healthy": healthy,
        "checkedAt": utcnow(),
        "sqliteIntegrity": sqlite_integrity,
        "foreignKeyViolations": len(foreign_key_rows),
        "verifiedRecords": verified_records,
        "recordFailures": record_failures,
        "verifiedAuditEvents": verified_audit_events,
        "auditFailures": audit_failures,
        "auditHead": previous_hash if audit_rows else None,
        "databaseMode": oct(mode) if mode is not None else None,
        "truthLabel": (
            "cryptographic and structural integrity verification; this does not validate "
            "the factual quality of stored scenarios or model opinions"
        ),
    }


def retention_plan(
    token: str,
    *,
    store: EncryptedSQLiteStore | None = None,
    overrides: dict[str, int] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    store = store or STORAGE.sqlite
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = _retention_policy(overrides)
    records = _all_active_records(token, store)
    candidates: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []

    for record in records:
        age_days = max(0.0, (current - _parse_time(record.updated_at)).total_seconds() / 86400.0)
        retention_days = policy.get(record.record_type, policy["default"])
        is_held, hold_reason = _held(record)
        item = {
            **_record_view(record),
            "ageDays": round(age_days, 3),
            "retentionDays": retention_days,
        }
        if is_held:
            item["holdReason"] = hold_reason
            held.append(item)
        elif age_days >= retention_days:
            item["reason"] = "updatedAt exceeds the configured retention window"
            candidates.append(item)

    candidates.sort(key=lambda item: float(item["ageDays"]), reverse=True)
    return {
        "dryRun": True,
        "generatedAt": current.isoformat(),
        "policyDays": policy,
        "candidateCount": len(candidates),
        "heldCount": len(held),
        "candidates": candidates,
        "held": held,
        "confirmationRequired": RETENTION_CONFIRMATION,
        "truthLabel": "deterministic local retention plan; no records were deleted",
    }


def apply_retention(
    token: str,
    *,
    confirmation: str,
    store: EncryptedSQLiteStore | None = None,
    overrides: dict[str, int] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if confirmation != RETENTION_CONFIRMATION:
        raise GovernanceError(
            f"Destructive retention requires exact confirmation: {RETENTION_CONFIRMATION}"
        )
    store = store or STORAGE.sqlite
    plan = retention_plan(token, store=store, overrides=overrides, now=now)
    deleted: list[str] = []
    failures: list[dict[str, str]] = []
    for candidate in plan["candidates"]:
        record_id = str(candidate["recordId"])
        try:
            if store.delete(token, record_id):
                deleted.append(record_id)
        except Exception as exc:
            failures.append(
                {"recordId": record_id, "error": f"{type(exc).__name__}: {exc}"}
            )
    return {
        "applied": True,
        "appliedAt": utcnow(),
        "deletedCount": len(deleted),
        "deletedRecordIds": deleted,
        "failures": failures,
        "heldCount": int(plan["heldCount"]),
        "weaviateDeletionQueue": store.status()["pendingSync"],
        "truthLabel": "confirmed local retention deletion with encrypted audit events",
    }


def _references(value: Any) -> set[str]:
    found: set[str] = set()

    def walk(child: Any, key: str | None = None) -> None:
        if key in REFERENCE_KEYS:
            if isinstance(child, str) and child:
                found.add(child)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, str) and item:
                        found.add(item)
                    elif isinstance(item, dict):
                        for nested in item.values():
                            if isinstance(nested, str) and nested:
                                found.add(nested)
            elif isinstance(child, dict):
                for nested in child.values():
                    if isinstance(nested, str) and nested:
                        found.add(nested)
        if isinstance(child, dict):
            for nested_key, nested in child.items():
                walk(nested, str(nested_key))
        elif isinstance(child, list):
            for nested in child:
                walk(nested, key)

    walk(value)
    return found


def provenance_graph(
    token: str,
    record_id: str,
    *,
    store: EncryptedSQLiteStore | None = None,
    max_depth: int = 3,
    max_nodes: int = 128,
) -> dict[str, Any]:
    store = store or STORAGE.sqlite
    records = _all_active_records(token, store)
    by_id = {record.record_id: record for record in records}
    if record_id not in by_id:
        raise GovernanceError("Encrypted record was not found.")

    outgoing = {
        current.record_id: {
            reference for reference in _references(current.metadata) if reference in by_id
        }
        for current in records
    }
    incoming: dict[str, set[str]] = {current.record_id: set() for current in records}
    for source, targets in outgoing.items():
        for target in targets:
            incoming.setdefault(target, set()).add(source)

    depth_limit = max(0, min(8, int(max_depth)))
    node_limit = max(1, min(512, int(max_nodes)))
    queue: deque[tuple[str, int]] = deque([(record_id, 0)])
    visited: set[str] = set()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    edge_keys: set[tuple[str, str, str]] = set()

    while queue and len(nodes) < node_limit:
        current_id, depth = queue.popleft()
        if current_id in visited:
            continue
        visited.add(current_id)
        current = by_id[current_id]
        nodes.append({**_record_view(current), "depth": depth})
        if depth >= depth_limit:
            continue
        for target in sorted(outgoing.get(current_id, set())):
            key = (current_id, target, "derived-from")
            if key not in edge_keys:
                edges.append({"from": current_id, "to": target, "relation": "derived-from"})
                edge_keys.add(key)
            queue.append((target, depth + 1))
        for source in sorted(incoming.get(current_id, set())):
            key = (source, current_id, "derived-from")
            if key not in edge_keys:
                edges.append({"from": source, "to": current_id, "relation": "derived-from"})
                edge_keys.add(key)
            queue.append((source, depth + 1))

    return {
        "rootRecordId": record_id,
        "nodes": nodes,
        "edges": edges,
        "truncated": bool(queue),
        "maxDepth": depth_limit,
        "truthLabel": (
            "encrypted local provenance links explicitly declared in record metadata; "
            "absence of an edge does not prove independence"
        ),
    }


def queue_full_weaviate_rebuild(
    token: str,
    *,
    confirmation: str,
    store: EncryptedSQLiteStore | None = None,
) -> dict[str, Any]:
    if confirmation != REBUILD_CONFIRMATION:
        raise GovernanceError(
            f"Full projection rebuild requires exact confirmation: {REBUILD_CONFIRMATION}"
        )
    store = store or STORAGE.sqlite
    store._keys(token)
    store.initialize()
    queued_at = utcnow()
    with store._connect() as database:
        rows = database.execute(
            "SELECT record_id FROM records WHERE deleted = 0 ORDER BY updated_at ASC"
        ).fetchall()
        database.executemany(
            """
            INSERT INTO sync_queue(record_id, operation, attempts, last_error, queued_at)
            VALUES (?, 'upsert', 0, NULL, ?)
            ON CONFLICT(record_id) DO UPDATE SET
                operation='upsert', attempts=0, last_error=NULL, queued_at=excluded.queued_at
            """,
            [(str(row["record_id"]), queued_at) for row in rows],
        )
        database.commit()
    return {
        "queued": len(rows),
        "queuedAt": queued_at,
        "confirmation": confirmation,
        "truthLabel": (
            "all active encrypted records queued for regeneration of redacted Weaviate projections"
        ),
    }


def create_compaction_record(
    token: str,
    record_ids: Iterable[str],
    *,
    title: str,
    store: EncryptedSQLiteStore | None = None,
) -> StoredRecord:
    """Create a provenance-preserving deterministic digest record without deleting sources."""

    store = store or STORAGE.sqlite
    selected: list[StoredRecord] = []
    for record_id in dict.fromkeys(str(value) for value in record_ids):
        record = store.get(token, record_id)
        if record is None:
            raise GovernanceError(f"Source record not found: {record_id}")
        selected.append(record)
    if not selected:
        raise GovernanceError("At least one source record is required for compaction.")
    if len(selected) > 200:
        raise GovernanceError("A compaction record may reference at most 200 source records.")

    tag_counts: dict[str, int] = {}
    for record in selected:
        for tag in record.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = [
        tag
        for tag, _ in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:24]
    ]
    payload = {
        "schema": "cyberforge-memory-compaction-v1",
        "sourceRecordIds": [record.record_id for record in selected],
        "sourceDigests": {record.record_id: record.digest for record in selected},
        "sourceTypes": sorted({record.record_type for record in selected}),
        "topTags": top_tags,
        "entries": [
            {
                "recordId": record.record_id,
                "recordType": record.record_type,
                "title": record.title,
                "summary": record.summary,
                "truthLabel": record.truth_label,
                "validationStatus": record.validation_status,
                "updatedAt": record.updated_at,
                "digest": record.digest,
            }
            for record in selected
        ],
        "compactedAt": utcnow(),
        "boundary": (
            "This is a deterministic index-level compaction. It preserves source identifiers "
            "and digests and does not replace or delete source records."
        ),
    }
    return store.put(
        token,
        "memory-compaction",
        payload,
        truth_label="deterministic provenance-preserving memory compaction",
        validation_status="derived",
        title=title,
        summary=f"Compacted index for {len(selected)} encrypted CyberForge records.",
        tags=["memory-compaction", *top_tags],
        metadata={
            "sourceRecordIds": [record.record_id for record in selected],
            "sourceCount": len(selected),
            "retentionHold": True,
        },
    )
