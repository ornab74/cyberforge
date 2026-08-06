from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256, sha3_256
from pathlib import Path
from threading import RLock
from typing import Any, Iterable
from uuid import UUID, uuid4, uuid5
import asyncio
import base64
import hmac
import json
import math
import os
import re
import sqlite3

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import SETTINGS, ensure_directories
from .crypto import CryptoError, aes_gcm_decrypt, aes_gcm_encrypt
from .guardrails import redact_packet
from .vault import VAULT, SecureVault, VaultError


STORE_FORMAT = "cyberforge-encrypted-sqlite-v1"
WEAVIATE_SCHEMA = "CyberForgeMemoryV1"
WEAVIATE_NAMESPACE = UUID("d08fcfe2-a4d1-4aeb-8ad5-f741cc343d9e")
TOKEN_PATTERN = re.compile(r"[a-z0-9_./:-]{2,}", re.IGNORECASE)


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredRecord:
    record_id: str
    record_type: str
    created_at: str
    updated_at: str
    truth_label: str
    validation_status: str
    digest: str
    scope_hash: str
    title: str
    summary: str
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    payload: Any

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_payload:
            value.pop("payload", None)
        return value


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _tokens(text: str) -> list[str]:
    return sorted(set(match.group(0).lower()[:96] for match in TOKEN_PATTERN.finditer(text)))


def _scope_hash(scope: str) -> str:
    return sha3_256(scope.strip().lower().encode("utf-8")).hexdigest()[:32]


def _hkdf(master: bytes, purpose: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cyberforge-storage-v1",
        info=purpose.encode("utf-8"),
    ).derive(master)


def _feature_hash(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    tokens = _tokens(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        weight = 1.0 + min(2.0, len(token) / 16.0)
        vector[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _projection_text(record: StoredRecord) -> str:
    return " ".join(
        [
            record.record_type,
            record.title,
            record.summary,
            record.truth_label,
            record.validation_status,
            *record.tags,
            json.dumps(record.metadata, sort_keys=True),
        ]
    )


def _default_projection(record_type: str, payload: Any) -> tuple[str, str, list[str], dict[str, Any]]:
    redacted, redactions = redact_packet(payload)
    if isinstance(redacted, dict):
        title = str(
            redacted.get("name")
            or redacted.get("title")
            or redacted.get("schema")
            or record_type
        )[:240]
        summary_candidates = (
            redacted.get("summary"),
            redacted.get("description"),
            redacted.get("interpretation"),
        )
        summary = ""
        for candidate in summary_candidates:
            if isinstance(candidate, str) and candidate.strip():
                summary = candidate.strip()
                break
            if isinstance(candidate, dict):
                summary = json.dumps(candidate, sort_keys=True)
                break
        if not summary:
            summary = json.dumps(redacted, sort_keys=True)[:2000]
        tags = [record_type]
        for key in ("scale", "schema", "truthLabel", "validationStatus"):
            value = redacted.get(key)
            if isinstance(value, str) and value:
                tags.append(value[:96])
        metadata = {
            "redactions": redactions,
            "sourceKeys": sorted(str(key)[:80] for key in redacted.keys())[:48],
        }
        return title, summary[:4000], sorted(set(tags)), metadata
    return record_type, str(redacted)[:4000], [record_type], {"redactions": redactions}


class EncryptedSQLiteStore:
    """Vault-keyed encrypted system of record.

    SQLite stores only bounded routing metadata, digests, ciphertext, and keyed
    blind-search tokens. Titles, summaries, tags, metadata, and full payloads are
    encrypted independently with AES-256-GCM per record.
    """

    def __init__(self, path: Path | None = None, vault: SecureVault | None = None) -> None:
        ensure_directories()
        self.path = path or SETTINGS.storage_db
        self.vault = vault or VAULT
        self._lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        with self._connect() as database:
            database.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    truth_label TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    scope_hash TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    key_version INTEGER NOT NULL,
                    nonce TEXT NOT NULL,
                    ciphertext TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_records_type_time
                    ON records(record_type, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_records_scope_time
                    ON records(scope_hash, updated_at DESC);
                CREATE TABLE IF NOT EXISTS blind_tokens (
                    token_hash TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    PRIMARY KEY(token_hash, record_id),
                    FOREIGN KEY(record_id) REFERENCES records(record_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_blind_token_hash
                    ON blind_tokens(token_hash);
                CREATE TABLE IF NOT EXISTS sync_queue (
                    record_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    queued_at TEXT NOT NULL,
                    FOREIGN KEY(record_id) REFERENCES records(record_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS audit_chain (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    ciphertext TEXT NOT NULL
                );
                """
            )
            database.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        database = sqlite3.connect(self.path, timeout=30)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys=ON")
        database.execute("PRAGMA busy_timeout=5000")
        return database

    def _master_key(self, token: str) -> bytes:
        self.vault.validate_session(token)
        stored = self.vault.get_json("storage", "sqlite-master-key-v1")
        if stored is None:
            generated = os.urandom(32)
            self.vault.set_json(
                token,
                "storage",
                "sqlite-master-key-v1",
                {
                    "format": STORE_FORMAT,
                    "key": base64.b64encode(generated).decode("ascii"),
                    "createdAt": utcnow(),
                },
            )
            return generated
        try:
            key = base64.b64decode(str(stored["key"]), validate=True)
        except Exception as exc:
            raise StorageError("Encrypted SQLite master key is malformed.") from exc
        if len(key) != 32:
            raise StorageError("Encrypted SQLite master key has an invalid length.")
        return key

    def _keys(self, token: str) -> tuple[bytes, bytes, bytes]:
        master = self._master_key(token)
        return (
            _hkdf(master, "record-encryption"),
            _hkdf(master, "blind-index"),
            _hkdf(master, "audit-chain"),
        )

    @staticmethod
    def _blind_token(index_key: bytes, token: str) -> str:
        return hmac.new(index_key, token.encode("utf-8"), sha256).hexdigest()

    def put(
        self,
        token: str,
        record_type: str,
        payload: Any,
        *,
        record_id: str | None = None,
        scope: str = "default",
        truth_label: str = "operator-provided encrypted record",
        validation_status: str = "unverified",
        title: str | None = None,
        summary: str | None = None,
        tags: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
    ) -> StoredRecord:
        self.initialize()
        record_key, index_key, audit_key = self._keys(token)
        record_id = record_id or str(uuid4())
        now = utcnow()
        generated_title, generated_summary, generated_tags, generated_meta = _default_projection(
            record_type, payload
        )
        clear = {
            "title": (title or generated_title)[:240],
            "summary": (summary or generated_summary)[:8000],
            "tags": sorted(set(str(value)[:96] for value in [*generated_tags, *tags] if str(value))),
            "metadata": {**generated_meta, **(metadata or {})},
            "payload": payload,
        }
        digest = sha3_256(_canonical(clear)).hexdigest()
        aad = f"{STORE_FORMAT}:{record_id}:{record_type}:1".encode("utf-8")
        envelope = aes_gcm_encrypt(_canonical(clear), record_key, aad)
        scope_digest = _scope_hash(scope)
        searchable = " ".join(
            [
                record_type,
                truth_label,
                validation_status,
                clear["title"],
                clear["summary"],
                *clear["tags"],
                json.dumps(clear["metadata"], sort_keys=True),
            ]
        )
        with self._lock, self._connect() as database:
            existing = database.execute(
                "SELECT created_at FROM records WHERE record_id = ?", (record_id,)
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            database.execute(
                """
                INSERT INTO records (
                    record_id, record_type, created_at, updated_at, truth_label,
                    validation_status, scope_hash, digest, key_version, nonce,
                    ciphertext, deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0)
                ON CONFLICT(record_id) DO UPDATE SET
                    record_type=excluded.record_type,
                    updated_at=excluded.updated_at,
                    truth_label=excluded.truth_label,
                    validation_status=excluded.validation_status,
                    scope_hash=excluded.scope_hash,
                    digest=excluded.digest,
                    key_version=excluded.key_version,
                    nonce=excluded.nonce,
                    ciphertext=excluded.ciphertext,
                    deleted=0
                """,
                (
                    record_id,
                    record_type[:96],
                    created_at,
                    now,
                    truth_label[:160],
                    validation_status[:64],
                    scope_digest,
                    digest,
                    envelope["nonce"],
                    envelope["ciphertext"],
                ),
            )
            database.execute("DELETE FROM blind_tokens WHERE record_id = ?", (record_id,))
            database.executemany(
                "INSERT OR REPLACE INTO blind_tokens(token_hash, record_id, weight) VALUES (?, ?, ?)",
                [
                    (self._blind_token(index_key, word), record_id, 1.0)
                    for word in _tokens(searchable)
                ],
            )
            database.execute(
                """
                INSERT INTO sync_queue(record_id, operation, attempts, last_error, queued_at)
                VALUES (?, 'upsert', 0, NULL, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    operation='upsert', attempts=0, last_error=NULL, queued_at=excluded.queued_at
                """,
                (record_id, now),
            )
            self._append_audit(
                database,
                audit_key,
                "put",
                record_id,
                {"recordType": record_type, "digest": digest, "updatedAt": now},
            )
            database.commit()
        return StoredRecord(
            record_id=record_id,
            record_type=record_type,
            created_at=created_at,
            updated_at=now,
            truth_label=truth_label,
            validation_status=validation_status,
            digest=digest,
            scope_hash=scope_digest,
            title=clear["title"],
            summary=clear["summary"],
            tags=tuple(clear["tags"]),
            metadata=dict(clear["metadata"]),
            payload=payload,
        )

    def _append_audit(
        self,
        database: sqlite3.Connection,
        audit_key: bytes,
        operation: str,
        record_id: str,
        event: dict[str, Any],
    ) -> None:
        previous = database.execute(
            "SELECT event_hash FROM audit_chain ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous else "0" * 64
        clear = {"operation": operation, "recordId": record_id, "event": event}
        event_hash = sha3_256(previous_hash.encode("ascii") + _canonical(clear)).hexdigest()
        aad = f"{STORE_FORMAT}:audit:{event_hash}".encode("utf-8")
        envelope = aes_gcm_encrypt(_canonical(clear), audit_key, aad)
        database.execute(
            """
            INSERT INTO audit_chain(
                created_at, operation, record_id, previous_hash, event_hash, nonce, ciphertext
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utcnow(),
                operation,
                record_id,
                previous_hash,
                event_hash,
                envelope["nonce"],
                envelope["ciphertext"],
            ),
        )

    def _decode_row(self, token: str, row: sqlite3.Row) -> StoredRecord:
        record_key, _, _ = self._keys(token)
        aad = (
            f"{STORE_FORMAT}:{row['record_id']}:{row['record_type']}:{row['key_version']}"
        ).encode("utf-8")
        try:
            clear_bytes = aes_gcm_decrypt(
                {"nonce": row["nonce"], "ciphertext": row["ciphertext"]},
                record_key,
                aad,
            )
            clear = json.loads(clear_bytes.decode("utf-8"))
        except (CryptoError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageError(f"Record {row['record_id']} failed authentication.") from exc
        digest = sha3_256(_canonical(clear)).hexdigest()
        if not hmac.compare_digest(digest, str(row["digest"])):
            raise StorageError(f"Record {row['record_id']} digest mismatch.")
        return StoredRecord(
            record_id=str(row["record_id"]),
            record_type=str(row["record_type"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            truth_label=str(row["truth_label"]),
            validation_status=str(row["validation_status"]),
            digest=digest,
            scope_hash=str(row["scope_hash"]),
            title=str(clear.get("title", "")),
            summary=str(clear.get("summary", "")),
            tags=tuple(str(value) for value in clear.get("tags", [])),
            metadata=dict(clear.get("metadata", {})),
            payload=clear.get("payload"),
        )

    def get(self, token: str, record_id: str) -> StoredRecord | None:
        self.initialize()
        with self._connect() as database:
            row = database.execute(
                "SELECT * FROM records WHERE record_id = ? AND deleted = 0", (record_id,)
            ).fetchone()
        return None if row is None else self._decode_row(token, row)

    def list_records(
        self,
        token: str,
        *,
        limit: int = 100,
        record_type: str | None = None,
        include_payload: bool = False,
    ) -> list[dict[str, Any]]:
        self.initialize()
        limit = max(1, min(500, int(limit)))
        query = "SELECT * FROM records WHERE deleted = 0"
        arguments: list[Any] = []
        if record_type:
            query += " AND record_type = ?"
            arguments.append(record_type)
        query += " ORDER BY updated_at DESC LIMIT ?"
        arguments.append(limit)
        with self._connect() as database:
            rows = database.execute(query, arguments).fetchall()
        return [
            self._decode_row(token, row).to_dict(include_payload=include_payload)
            for row in rows
        ]

    def search(
        self,
        token: str,
        query: str,
        *,
        limit: int = 24,
        record_type: str | None = None,
    ) -> list[tuple[StoredRecord, float]]:
        self.initialize()
        _, index_key, _ = self._keys(token)
        words = _tokens(query)
        if not words:
            return []
        hashes = [self._blind_token(index_key, word) for word in words]
        placeholders = ",".join("?" for _ in hashes)
        sql = f"""
            SELECT r.*, SUM(bt.weight) AS matched
            FROM blind_tokens bt
            JOIN records r ON r.record_id = bt.record_id
            WHERE bt.token_hash IN ({placeholders}) AND r.deleted = 0
        """
        arguments: list[Any] = list(hashes)
        if record_type:
            sql += " AND r.record_type = ?"
            arguments.append(record_type)
        sql += " GROUP BY r.record_id ORDER BY matched DESC, r.updated_at DESC LIMIT ?"
        arguments.append(max(1, min(200, int(limit))))
        with self._connect() as database:
            rows = database.execute(sql, arguments).fetchall()
        results: list[tuple[StoredRecord, float]] = []
        for row in rows:
            matched = float(row["matched"] or 0.0)
            results.append((self._decode_row(token, row), matched / max(1.0, len(words))))
        return results

    def temporal_neighbors(
        self, token: str, record_id: str, *, radius: int = 2
    ) -> list[StoredRecord]:
        self.initialize()
        radius = max(0, min(10, int(radius)))
        if radius == 0:
            return []
        with self._connect() as database:
            rows = database.execute(
                "SELECT * FROM records WHERE deleted = 0 ORDER BY created_at ASC"
            ).fetchall()
        ids = [str(row["record_id"]) for row in rows]
        if record_id not in ids:
            return []
        index = ids.index(record_id)
        selected = rows[max(0, index - radius) : min(len(rows), index + radius + 1)]
        return [
            self._decode_row(token, row)
            for row in selected
            if str(row["record_id"]) != record_id
        ]

    def delete(self, token: str, record_id: str) -> bool:
        self.initialize()
        _, _, audit_key = self._keys(token)
        with self._lock, self._connect() as database:
            row = database.execute(
                "SELECT record_id FROM records WHERE record_id = ? AND deleted = 0", (record_id,)
            ).fetchone()
            if row is None:
                return False
            database.execute(
                "UPDATE records SET deleted = 1, updated_at = ? WHERE record_id = ?",
                (utcnow(), record_id),
            )
            database.execute("DELETE FROM blind_tokens WHERE record_id = ?", (record_id,))
            database.execute(
                """
                INSERT INTO sync_queue(record_id, operation, attempts, last_error, queued_at)
                VALUES (?, 'delete', 0, NULL, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    operation='delete', attempts=0, last_error=NULL, queued_at=excluded.queued_at
                """,
                (record_id, utcnow()),
            )
            self._append_audit(database, audit_key, "delete", record_id, {"deletedAt": utcnow()})
            database.commit()
            return True

    def pending_sync(self, *, limit: int = 200) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as database:
            rows = database.execute(
                "SELECT record_id, operation, attempts, last_error, queued_at "
                "FROM sync_queue ORDER BY queued_at ASC LIMIT ?",
                (max(1, min(1000, int(limit))),),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_synced(self, record_id: str) -> None:
        with self._connect() as database:
            database.execute("DELETE FROM sync_queue WHERE record_id = ?", (record_id,))
            database.commit()

    def mark_sync_failed(self, record_id: str, error: Exception) -> None:
        with self._connect() as database:
            database.execute(
                "UPDATE sync_queue SET attempts = attempts + 1, last_error = ? WHERE record_id = ?",
                (f"{type(error).__name__}: {error}"[:1000], record_id),
            )
            database.commit()

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self._connect() as database:
            record_count = int(
                database.execute("SELECT COUNT(*) FROM records WHERE deleted = 0").fetchone()[0]
            )
            pending_count = int(database.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0])
            audit_count = int(database.execute("SELECT COUNT(*) FROM audit_chain").fetchone()[0])
            last_hash_row = database.execute(
                "SELECT event_hash FROM audit_chain ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        return {
            "backend": "sqlite",
            "path": str(self.path),
            "recordCount": record_count,
            "pendingSync": pending_count,
            "auditEvents": audit_count,
            "auditHead": str(last_hash_row[0]) if last_hash_row else None,
            "recordEncryption": "AES-256-GCM per record with vault-wrapped master key",
            "searchIndex": "HMAC-SHA-256 blind tokens; no plaintext titles or summaries",
            "fileMode": oct(self.path.stat().st_mode & 0o777) if self.path.exists() else None,
        }


class WeaviateIndex:
    """Redacted, reconstructible search index.

    The full payload never enters Weaviate. Every indexed object can be rebuilt
    from the encrypted SQLite source of truth.
    """

    def __init__(self) -> None:
        self.client: Any = None
        self.mode = "uninitialized"
        self.status_message = "uninitialized"

    def _collection(self):
        if self.client is None:
            raise StorageError("Weaviate client is not initialized.")
        return self.client.collections.use(SETTINGS.weaviate_collection)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        requested = SETTINGS.weaviate_mode
        if requested == "off":
            self.mode = "off"
            self.status_message = "disabled by configuration"
            return
        try:
            import weaviate
        except ImportError as exc:
            self.mode = "unavailable"
            self.status_message = "weaviate-client is not installed"
            if requested in {"remote", "embedded"}:
                raise StorageError(
                    "Install optional memory support with sidecar/requirements-memory.txt"
                ) from exc
            return

        errors: list[str] = []
        if requested in {"auto", "remote"}:
            try:
                self.client = self._connect_remote(weaviate)
                self.mode = "remote"
                self._validate_ready()
                return
            except Exception as exc:
                errors.append(f"remote={type(exc).__name__}: {exc}")
                self._close_sync()
                if requested == "remote":
                    raise StorageError(errors[-1]) from exc
        if requested in {"auto", "embedded"}:
            try:
                self.client = self._connect_embedded(weaviate)
                self.mode = "embedded"
                self._validate_ready()
                return
            except Exception as exc:
                errors.append(f"embedded={type(exc).__name__}: {exc}")
                self._close_sync()
                if requested == "embedded":
                    raise StorageError(errors[-1]) from exc
        self.mode = "unavailable"
        self.status_message = "; ".join(errors) or "no Weaviate mode succeeded"

    @staticmethod
    def _auth_credentials(api_key: str):
        if not api_key:
            return None
        try:
            from weaviate.classes.init import Auth

            return Auth.api_key(api_key)
        except ImportError:
            from weaviate.auth import AuthApiKey

            return AuthApiKey(api_key)

    def _connect_remote(self, weaviate: Any):
        kwargs: dict[str, Any] = {}
        auth = self._auth_credentials(SETTINGS.weaviate_api_key)
        if auth is not None:
            kwargs["auth_credentials"] = auth
        return weaviate.connect_to_custom(
            http_host=SETTINGS.weaviate_http_host,
            http_port=SETTINGS.weaviate_http_port,
            http_secure=SETTINGS.weaviate_secure,
            grpc_host=SETTINGS.weaviate_grpc_host,
            grpc_port=SETTINGS.weaviate_grpc_port,
            grpc_secure=SETTINGS.weaviate_secure,
            **kwargs,
        )

    def _connect_embedded(self, weaviate: Any):
        SETTINGS.weaviate_embedded_data_path.mkdir(parents=True, exist_ok=True)
        SETTINGS.weaviate_embedded_binary_path.mkdir(parents=True, exist_ok=True)
        return weaviate.connect_to_embedded(
            hostname="127.0.0.1",
            port=SETTINGS.weaviate_embedded_http_port,
            grpc_port=SETTINGS.weaviate_embedded_grpc_port,
            version=SETTINGS.weaviate_embedded_version,
            persistence_data_path=str(SETTINGS.weaviate_embedded_data_path.resolve()),
            binary_path=str(SETTINGS.weaviate_embedded_binary_path.resolve()),
            environment_variables={
                "LOG_LEVEL": SETTINGS.weaviate_embedded_log_level,
                "DISABLE_TELEMETRY": "true",
                "QUERY_DEFAULTS_LIMIT": "50",
            },
        )

    def _validate_ready(self) -> None:
        if self.client is None or not self.client.is_ready():
            raise StorageError("Weaviate liveness check failed.")
        self._ensure_collection()
        self._crud_sentinel()
        self.status_message = f"{self.mode}: healthy (liveness + schema + CRUD + hybrid)"

    def _ensure_collection(self) -> None:
        from weaviate.classes.config import Configure, DataType, Property, VectorDistances

        if self.client.collections.exists(SETTINGS.weaviate_collection):
            return
        hnsw = Configure.VectorIndex.hnsw(
            distance_metric=VectorDistances.COSINE,
            ef_construction=128,
            max_connections=32,
        )
        self.client.collections.create(
            name=SETTINGS.weaviate_collection,
            description=(
                "Redacted CyberForge search projections. Encrypted SQLite remains the source of truth."
            ),
            vector_config=[
                Configure.Vectors.self_provided(name="content", vector_index_config=hnsw),
                Configure.Vectors.self_provided(
                    name="topology",
                    vector_index_config=Configure.VectorIndex.hnsw(
                        distance_metric=VectorDistances.COSINE,
                        ef_construction=96,
                        max_connections=24,
                    ),
                ),
            ],
            properties=[
                Property(name="record_id", data_type=DataType.TEXT),
                Property(name="record_type", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="summary", data_type=DataType.TEXT),
                Property(name="truth_label", data_type=DataType.TEXT),
                Property(name="validation_status", data_type=DataType.TEXT),
                Property(name="scope_hash", data_type=DataType.TEXT),
                Property(name="digest", data_type=DataType.TEXT),
                Property(name="tags", data_type=DataType.TEXT_ARRAY),
                Property(name="created_at", data_type=DataType.DATE),
                Property(name="updated_at", data_type=DataType.DATE),
                Property(name="metadata_json", data_type=DataType.TEXT),
                Property(name="redacted_projection", data_type=DataType.BOOL),
            ],
        )

    def _crud_sentinel(self) -> None:
        collection = self._collection()
        sentinel = f"cyberforge-health-{uuid4()}"
        object_id = uuid5(WEAVIATE_NAMESPACE, sentinel)
        vector = _feature_hash(sentinel)
        try:
            collection.data.insert(
                uuid=object_id,
                properties={
                    "record_id": sentinel,
                    "record_type": "health",
                    "title": sentinel,
                    "summary": sentinel,
                    "truth_label": "health sentinel",
                    "validation_status": "verified",
                    "scope_hash": _scope_hash("health"),
                    "digest": sha3_256(sentinel.encode()).hexdigest(),
                    "tags": ["health"],
                    "created_at": utcnow(),
                    "updated_at": utcnow(),
                    "metadata_json": "{}",
                    "redacted_projection": True,
                },
                vector={"content": vector, "topology": vector},
            )
            fetched = collection.query.fetch_object_by_id(object_id)
            if fetched is None or fetched.properties.get("record_id") != sentinel:
                raise StorageError("Weaviate CRUD read-back failed.")
            result = collection.query.hybrid(
                query=sentinel,
                vector=vector,
                target_vector="content",
                alpha=0.45,
                limit=1,
            )
            if not result.objects:
                raise StorageError("Weaviate hybrid sentinel query failed.")
        finally:
            try:
                collection.data.delete_by_id(object_id)
            except Exception:
                pass

    def upsert(self, record: StoredRecord) -> None:
        if self.client is None:
            raise StorageError("Weaviate is not available.")
        collection = self._collection()
        object_id = uuid5(WEAVIATE_NAMESPACE, record.record_id)
        properties = {
            "record_id": record.record_id,
            "record_type": record.record_type,
            "title": record.title,
            "summary": record.summary,
            "truth_label": record.truth_label,
            "validation_status": record.validation_status,
            "scope_hash": record.scope_hash,
            "digest": record.digest,
            "tags": list(record.tags),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "metadata_json": json.dumps(record.metadata, sort_keys=True)[:12000],
            "redacted_projection": True,
        }
        content_text = _projection_text(record)
        topology_text = " ".join(
            [record.record_type, record.title, *record.tags, json.dumps(record.metadata, sort_keys=True)]
        )
        try:
            collection.data.delete_by_id(object_id)
        except Exception:
            pass
        collection.data.insert(
            uuid=object_id,
            properties=properties,
            vector={
                "content": _feature_hash(content_text),
                "topology": _feature_hash(topology_text),
            },
        )

    def delete(self, record_id: str) -> None:
        if self.client is None:
            raise StorageError("Weaviate is not available.")
        self._collection().data.delete_by_id(uuid5(WEAVIATE_NAMESPACE, record_id))

    def search(
        self, query: str, *, limit: int = 24, record_type: str | None = None
    ) -> list[dict[str, Any]]:
        if self.client is None:
            return []
        from weaviate.classes.query import Filter, MetadataQuery

        filters = None
        if record_type:
            filters = Filter.by_property("record_type").equal(record_type)
        vector = _feature_hash(query)
        try:
            result = self._collection().query.hybrid(
                query=query,
                vector=vector,
                target_vector="content",
                alpha=SETTINGS.weaviate_hybrid_alpha,
                filters=filters,
                limit=max(1, min(200, int(limit))),
                return_metadata=MetadataQuery(score=True, explain_score=True),
            )
        except Exception:
            result = self._collection().query.bm25(
                query=query,
                query_properties=["title", "summary", "tags"],
                filters=filters,
                limit=max(1, min(200, int(limit))),
                return_metadata=MetadataQuery(score=True),
            )
        output: list[dict[str, Any]] = []
        for rank, obj in enumerate(result.objects, start=1):
            properties = obj.properties or {}
            output.append(
                {
                    "recordId": str(properties.get("record_id", "")),
                    "rank": rank,
                    "score": float(getattr(obj.metadata, "score", 0.0) or 0.0),
                    "properties": properties,
                }
            )
        return output

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            finally:
                self.client = None

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status_message,
            "collection": SETTINGS.weaviate_collection,
            "schema": WEAVIATE_SCHEMA,
            "payloadBoundary": "redacted projections only; encrypted SQLite is authoritative",
            "vectors": ["content", "topology"],
            "retrieval": "Weaviate hybrid + SQLite blind lexical, reciprocal-rank fusion, MMR diversity",
        }


class StorageCoordinator:
    def __init__(self, sqlite_store: EncryptedSQLiteStore | None = None) -> None:
        self.sqlite = sqlite_store or EncryptedSQLiteStore()
        self.weaviate = WeaviateIndex()
        self._weaviate_lock = asyncio.Lock()

    async def initialize_weaviate(self) -> dict[str, Any]:
        async with self._weaviate_lock:
            if self.weaviate.mode in {"uninitialized", "unavailable"}:
                await self.weaviate.initialize()
        return self.weaviate.status()

    async def put(self, token: str, record_type: str, payload: Any, **metadata: Any) -> StoredRecord:
        record = await asyncio.to_thread(
            self.sqlite.put, token, record_type, payload, **metadata
        )
        if SETTINGS.weaviate_mode != "off":
            try:
                await self.initialize_weaviate()
                if self.weaviate.client is not None:
                    await asyncio.to_thread(self.weaviate.upsert, record)
                    await asyncio.to_thread(self.sqlite.mark_synced, record.record_id)
            except Exception as exc:
                await asyncio.to_thread(self.sqlite.mark_sync_failed, record.record_id, exc)
        return record

    async def sync(self, token: str, *, limit: int = 200) -> dict[str, Any]:
        await self.initialize_weaviate()
        if self.weaviate.client is None:
            return {"synced": 0, "failed": 0, "status": self.weaviate.status()}
        pending = await asyncio.to_thread(self.sqlite.pending_sync, limit=limit)
        synced = failed = 0
        for item in pending:
            record_id = str(item["record_id"])
            try:
                if item["operation"] == "delete":
                    await asyncio.to_thread(self.weaviate.delete, record_id)
                else:
                    record = await asyncio.to_thread(self.sqlite.get, token, record_id)
                    if record is not None:
                        await asyncio.to_thread(self.weaviate.upsert, record)
                await asyncio.to_thread(self.sqlite.mark_synced, record_id)
                synced += 1
            except Exception as exc:
                await asyncio.to_thread(self.sqlite.mark_sync_failed, record_id, exc)
                failed += 1
        return {"synced": synced, "failed": failed, "status": self.weaviate.status()}

    async def search(
        self,
        token: str,
        query: str,
        *,
        limit: int = 8,
        record_type: str | None = None,
        temporal_radius: int = 1,
    ) -> list[dict[str, Any]]:
        candidate_limit = max(limit * 4, 24)
        sqlite_hits = await asyncio.to_thread(
            self.sqlite.search,
            token,
            query,
            limit=candidate_limit,
            record_type=record_type,
        )
        weaviate_hits: list[dict[str, Any]] = []
        if SETTINGS.weaviate_mode != "off":
            try:
                await self.initialize_weaviate()
                weaviate_hits = await asyncio.to_thread(
                    self.weaviate.search,
                    query,
                    limit=candidate_limit,
                    record_type=record_type,
                )
            except Exception:
                weaviate_hits = []

        rrf: dict[str, float] = defaultdict(float)
        records: dict[str, StoredRecord] = {}
        for rank, (record, _) in enumerate(sqlite_hits, start=1):
            records[record.record_id] = record
            rrf[record.record_id] += 1.0 / (SETTINGS.memory_rrf_k + rank)
        for item in weaviate_hits:
            record_id = str(item.get("recordId", ""))
            if not record_id:
                continue
            rrf[record_id] += 1.0 / (SETTINGS.memory_rrf_k + int(item.get("rank", 1)))
            if record_id not in records:
                record = await asyncio.to_thread(self.sqlite.get, token, record_id)
                if record is not None:
                    records[record_id] = record

        expanded = dict(records)
        for record in list(records.values())[:limit]:
            neighbors = await asyncio.to_thread(
                self.sqlite.temporal_neighbors,
                token,
                record.record_id,
                radius=temporal_radius,
            )
            for neighbor in neighbors:
                expanded.setdefault(neighbor.record_id, neighbor)
                rrf[neighbor.record_id] += 0.15 / (SETTINGS.memory_rrf_k + 1)

        query_vector = _feature_hash(query)
        vectors = {
            record_id: _feature_hash(_projection_text(record))
            for record_id, record in expanded.items()
        }
        candidates = sorted(expanded, key=lambda record_id: rrf.get(record_id, 0.0), reverse=True)
        selected: list[str] = []
        while candidates and len(selected) < max(1, min(50, limit)):
            best_id = max(
                candidates,
                key=lambda record_id: (
                    SETTINGS.memory_mmr_lambda
                    * (rrf.get(record_id, 0.0) + max(0.0, _cosine(query_vector, vectors[record_id])))
                    - (1.0 - SETTINGS.memory_mmr_lambda)
                    * max(
                        [_cosine(vectors[record_id], vectors[chosen]) for chosen in selected]
                        or [0.0]
                    )
                ),
            )
            selected.append(best_id)
            candidates.remove(best_id)

        return [
            {
                **expanded[record_id].to_dict(include_payload=False),
                "retrievalScore": rrf.get(record_id, 0.0),
                "retrieval": "RRF fusion with MMR diversity and temporal expansion",
            }
            for record_id in selected
        ]

    async def context_packet(
        self,
        token: str,
        query: str,
        *,
        limit: int = 6,
        record_type: str | None = None,
    ) -> dict[str, Any]:
        hits = await self.search(token, query, limit=limit, record_type=record_type)
        return {
            "query": query,
            "hits": hits,
            "truthLabel": "retrieved redacted projections from encrypted local records",
            "backendStatus": {
                "sqlite": self.sqlite.status(),
                "weaviate": self.weaviate.status(),
            },
        }

    async def delete(self, token: str, record_id: str) -> bool:
        deleted = await asyncio.to_thread(self.sqlite.delete, token, record_id)
        if deleted and self.weaviate.client is not None:
            try:
                await asyncio.to_thread(self.weaviate.delete, record_id)
                await asyncio.to_thread(self.sqlite.mark_synced, record_id)
            except Exception as exc:
                await asyncio.to_thread(self.sqlite.mark_sync_failed, record_id, exc)
        return deleted

    def status(self) -> dict[str, Any]:
        return {"sqlite": self.sqlite.status(), "weaviate": self.weaviate.status()}


STORAGE = StorageCoordinator()


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise StorageError("A valid unlocked-vault bearer session is required.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        VAULT.validate_session(token)
    except VaultError as exc:
        raise StorageError(str(exc)) from exc
    return token
