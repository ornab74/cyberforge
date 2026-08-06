from pathlib import Path

from cyberforge_sidecar.config import SETTINGS
from cyberforge_sidecar.storage import EncryptedSQLiteStore
from cyberforge_sidecar.vault import SecureVault


def test_encrypted_sqlite_roundtrip_search_and_plaintext_absence(tmp_path: Path):
    original = SETTINGS.data_dir
    object.__setattr__(SETTINGS, "data_dir", tmp_path)
    try:
        vault = SecureVault()
        token = vault.create("correct horse battery staple")
        store = EncryptedSQLiteStore(vault=vault)
        secret_marker = "synthetic-sensitive-marker-7f04e4"
        record = store.put(
            token,
            "research-run",
            {
                "name": "Synthetic identity pressure run",
                "summary": f"Contains {secret_marker}",
                "findings": ["phishing-resistant MFA coverage gap"],
            },
            truth_label="counterfactual simulation",
            validation_status="signed",
            tags=["identity", "mfa"],
        )

        loaded = store.get(token, record.record_id)
        assert loaded is not None
        assert loaded.payload["summary"].endswith(secret_marker)
        assert loaded.digest == record.digest

        hits = store.search(token, "identity MFA", limit=8)
        assert hits
        assert hits[0][0].record_id == record.record_id

        raw_database = SETTINGS.storage_db.read_bytes()
        assert secret_marker.encode() not in raw_database
        assert b"Synthetic identity pressure run" not in raw_database
        assert b"phishing-resistant MFA coverage gap" not in raw_database

        status = store.status()
        assert status["recordCount"] == 1
        assert status["auditEvents"] == 1
        assert status["pendingSync"] == 1
        assert status["recordEncryption"].startswith("AES-256-GCM")
    finally:
        object.__setattr__(SETTINGS, "data_dir", original)


def test_encrypted_sqlite_tamper_detection(tmp_path: Path):
    original = SETTINGS.data_dir
    object.__setattr__(SETTINGS, "data_dir", tmp_path)
    try:
        vault = SecureVault()
        token = vault.create("correct horse battery staple")
        store = EncryptedSQLiteStore(vault=vault)
        record = store.put(token, "scenario", {"name": "Synthetic scenario"})

        with store._connect() as database:  # focused corruption test
            row = database.execute(
                "SELECT ciphertext FROM records WHERE record_id = ?", (record.record_id,)
            ).fetchone()
            ciphertext = str(row["ciphertext"])
            replacement = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
            database.execute(
                "UPDATE records SET ciphertext = ? WHERE record_id = ?",
                (replacement, record.record_id),
            )
            database.commit()

        try:
            store.get(token, record.record_id)
            assert False, "tampered ciphertext must not decrypt"
        except Exception as exc:
            assert "failed authentication" in str(exc).lower()
    finally:
        object.__setattr__(SETTINGS, "data_dir", original)
