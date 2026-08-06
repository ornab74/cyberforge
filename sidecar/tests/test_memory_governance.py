from datetime import datetime, timedelta, timezone
from pathlib import Path

from cyberforge_sidecar.config import SETTINGS
from cyberforge_sidecar.memory_governance import (
    RETENTION_CONFIRMATION,
    apply_retention,
    create_compaction_record,
    provenance_graph,
    queue_full_weaviate_rebuild,
    retention_plan,
    verify_integrity,
)
from cyberforge_sidecar.storage import EncryptedSQLiteStore
from cyberforge_sidecar.vault import SecureVault


def _setup(tmp_path: Path):
    original = SETTINGS.data_dir
    object.__setattr__(SETTINGS, "data_dir", tmp_path)
    vault = SecureVault()
    token = vault.create("correct horse battery staple")
    store = EncryptedSQLiteStore(vault=vault)
    return original, vault, token, store


def test_integrity_verifies_records_and_audit_chain(tmp_path: Path):
    original, _, token, store = _setup(tmp_path)
    try:
        store.put(token, "scenario", {"name": "Integrity scenario"})
        store.put(token, "report", {"summary": "Integrity report"})

        report = verify_integrity(token, store=store)
        assert report["healthy"] is True
        assert report["verifiedRecords"] == 2
        assert report["verifiedAuditEvents"] == 2
        assert report["recordFailures"] == []
        assert report["auditFailures"] == []
        assert report["databaseMode"] == "0o600"
    finally:
        object.__setattr__(SETTINGS, "data_dir", original)


def test_retention_dry_run_preserves_holds_and_requires_confirmation(tmp_path: Path):
    original, _, token, store = _setup(tmp_path)
    try:
        expired = store.put(
            token,
            "health",
            {"summary": "old disposable health record"},
        )
        held = store.put(
            token,
            "health",
            {"summary": "old held health record"},
            tags=["legal-hold"],
        )
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with store._connect() as database:
            database.execute(
                "UPDATE records SET updated_at = ? WHERE record_id IN (?, ?)",
                (old, expired.record_id, held.record_id),
            )
            database.commit()

        plan = retention_plan(token, store=store, overrides={"health": 7})
        assert plan["dryRun"] is True
        assert [item["recordId"] for item in plan["candidates"]] == [expired.record_id]
        assert [item["recordId"] for item in plan["held"]] == [held.record_id]
        assert store.get(token, expired.record_id) is not None

        try:
            apply_retention(
                token,
                confirmation="wrong",
                store=store,
                overrides={"health": 7},
            )
            assert False, "retention must require exact confirmation"
        except Exception as exc:
            assert RETENTION_CONFIRMATION in str(exc)

        applied = apply_retention(
            token,
            confirmation=RETENTION_CONFIRMATION,
            store=store,
            overrides={"health": 7},
        )
        assert applied["deletedRecordIds"] == [expired.record_id]
        assert store.get(token, expired.record_id) is None
        assert store.get(token, held.record_id) is not None
    finally:
        object.__setattr__(SETTINGS, "data_dir", original)


def test_compaction_preserves_provenance_and_rebuild_queue(tmp_path: Path):
    original, _, token, store = _setup(tmp_path)
    try:
        source = store.put(
            token,
            "scenario",
            {"name": "Source scenario"},
            tags=["identity"],
        )
        derived = store.put(
            token,
            "research-run",
            {"summary": "Derived run"},
            tags=["identity", "research"],
            metadata={"sourceRecordIds": [source.record_id]},
        )
        compacted = create_compaction_record(
            token,
            [source.record_id, derived.record_id],
            title="Identity research compact",
            store=store,
        )

        graph = provenance_graph(
            token,
            compacted.record_id,
            store=store,
            max_depth=3,
        )
        ids = {node["recordId"] for node in graph["nodes"]}
        assert {source.record_id, derived.record_id, compacted.record_id} <= ids
        assert any(
            edge["from"] == compacted.record_id and edge["to"] == source.record_id
            for edge in graph["edges"]
        )
        assert compacted.metadata["retentionHold"] is True
        assert store.get(token, source.record_id) is not None

        queued = queue_full_weaviate_rebuild(
            token,
            confirmation="REBUILD CYBERFORGE WEAVIATE",
            store=store,
        )
        assert queued["queued"] == 3
        assert store.status()["pendingSync"] == 3
    finally:
        object.__setattr__(SETTINGS, "data_dir", original)
