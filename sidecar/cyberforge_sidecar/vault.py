from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Optional
import base64
import hashlib
import json
import os
import secrets
import time

from .config import SETTINGS, ensure_directories
from .crypto import ArgonPolicy, CryptoError, aes_gcm_decrypt, aes_gcm_encrypt, derive_password_key

VAULT_FORMAT = "cyberforge-provider-vault-v3"
HEADER_NAME = "vault.header.json"
KEYRING_NAME = "vault.keyring.json"
RECORDS_NAME = "vault.records.json"
DEVICE_KEY_NAME = "device-unlock.key"


class VaultError(RuntimeError):
    pass


@dataclass(frozen=True)
class VaultStatus:
    exists: bool
    unlocked: bool
    session_count: int
    provider_ids: tuple[str, ...]
    password_required: bool
    active_data_key_id: int | None


class SecureVault:
    """Record-level AES-256-GCM vault for provider keys and local settings.

    The password/device wrapping layer protects a stable random root key. A
    separate authenticated keyring, encrypted by that root key, holds the
    keyed record-index secret and rotatable data-encryption keys. Each record
    receives an independent AES-GCM nonce and authenticated record identifier.
    """

    def __init__(self) -> None:
        ensure_directories()
        self._lock = RLock()
        self._root_key: Optional[bytearray] = None
        self._index_key: Optional[bytearray] = None
        self._data_keys: dict[int, bytearray] = {}
        self._active_data_key_id: Optional[int] = None
        self._sessions: dict[str, float] = {}

    @property
    def header_path(self) -> Path:
        return SETTINGS.vault_dir / HEADER_NAME

    @property
    def keyring_path(self) -> Path:
        return SETTINGS.vault_dir / KEYRING_NAME

    @property
    def records_path(self) -> Path:
        return SETTINGS.vault_dir / RECORDS_NAME

    @property
    def device_key_path(self) -> Path:
        return SETTINGS.vault_dir / DEVICE_KEY_NAME

    def status(self) -> VaultStatus:
        with self._lock:
            provider_ids: tuple[str, ...] = ()
            if self._root_key is not None:
                provider_ids = tuple(sorted(self._list_provider_ids()))
            header = self._read_header_optional()
            return VaultStatus(
                exists=header is not None,
                unlocked=self._root_key is not None,
                session_count=len(self._live_sessions()),
                provider_ids=provider_ids,
                password_required=bool(header.get("passwordRequired", True)) if header else True,
                active_data_key_id=self._active_data_key_id,
            )

    def create(self, password: str, *, password_required: bool = True) -> str:
        with self._lock:
            if self.header_path.exists():
                raise VaultError("A CyberForge vault already exists.")
            policy = ArgonPolicy()
            salt = os.urandom(policy.salt_bytes)
            password_key = derive_password_key(password, salt, policy)
            root_key = os.urandom(32)
            device_key = os.urandom(32)
            header = {
                "format": VAULT_FORMAT,
                "passwordRequired": password_required,
                "kdf": {
                    "algorithm": "Argon2id-1.3",
                    "salt": base64.b64encode(salt).decode(),
                    "memoryKiB": policy.memory_kib,
                    "iterations": policy.iterations,
                    "parallelism": policy.parallelism,
                },
                "passwordWrappedRoot": aes_gcm_encrypt(
                    root_key,
                    password_key,
                    f"{VAULT_FORMAT}:password-root".encode(),
                ),
                "deviceWrappedRoot": aes_gcm_encrypt(
                    root_key,
                    device_key,
                    f"{VAULT_FORMAT}:device-root".encode(),
                ),
                "createdAtUnix": int(time.time()),
                "version": 3,
            }
            self._atomic_json(self.header_path, header)
            self.device_key_path.write_bytes(device_key)
            try:
                self.device_key_path.chmod(0o600)
            except OSError:
                pass
            self._root_key = bytearray(root_key)
            self._index_key = bytearray(os.urandom(32))
            self._data_keys = {1: bytearray(os.urandom(32))}
            self._active_data_key_id = 1
            self._persist_keyring()
            self._atomic_json(self.records_path, {"format": VAULT_FORMAT, "records": {}})
            return self._new_session()

    def unlock(self, password: str) -> str:
        with self._lock:
            header = self._read_header()
            kdf = dict(header["kdf"])
            policy = ArgonPolicy(
                memory_kib=int(kdf["memoryKiB"]),
                iterations=int(kdf["iterations"]),
                parallelism=int(kdf["parallelism"]),
                salt_bytes=len(base64.b64decode(kdf["salt"])),
            )
            try:
                password_key = derive_password_key(
                    password,
                    base64.b64decode(kdf["salt"]),
                    policy,
                )
                root_key = aes_gcm_decrypt(
                    dict(header["passwordWrappedRoot"]),
                    password_key,
                    f"{VAULT_FORMAT}:password-root".encode(),
                )
            except CryptoError as exc:
                raise VaultError("Vault unlock failed.") from exc
            self._install_root_key(root_key)
            return self._new_session()

    def unlock_with_device_key(self) -> str:
        with self._lock:
            header = self._read_header()
            if not self.device_key_path.exists():
                raise VaultError("Device unlock key is unavailable.")
            try:
                root_key = aes_gcm_decrypt(
                    dict(header["deviceWrappedRoot"]),
                    self.device_key_path.read_bytes(),
                    f"{VAULT_FORMAT}:device-root".encode(),
                )
            except CryptoError as exc:
                raise VaultError("Device unlock failed.") from exc
            self._install_root_key(root_key)
            return self._new_session()

    def lock(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._zero(self._root_key)
            self._zero(self._index_key)
            for key in self._data_keys.values():
                self._zero(key)
            self._root_key = None
            self._index_key = None
            self._data_keys.clear()
            self._active_data_key_id = None

    def validate_session(self, token: str) -> None:
        with self._lock:
            self._live_sessions()
            expiry = self._sessions.get(token)
            if expiry is None or expiry <= time.time():
                raise VaultError("Vault session is missing or expired.")
            self._sessions[token] = time.time() + SETTINGS.session_ttl_seconds

    def set_secret(self, token: str, provider_id: str, secret: str) -> None:
        self.validate_session(token)
        provider_id = self._normalize_provider(provider_id)
        if not secret or len(secret) > 64 * 1024:
            raise VaultError("Provider secret is empty or too large.")
        self._write_record(
            f"provider:{provider_id}",
            {"value": secret, "updatedAt": int(time.time())},
        )

    def delete_secret(self, token: str, provider_id: str) -> None:
        self.validate_session(token)
        provider_id = self._normalize_provider(provider_id)
        self._delete_record(f"provider:{provider_id}")

    def get_secret(self, provider_id: str) -> Optional[str]:
        provider_id = self._normalize_provider(provider_id)
        value = self._read_record(f"provider:{provider_id}")
        return None if value is None else str(value.get("value", ""))

    def provider_configured(self, provider_id: str) -> bool:
        try:
            return bool(self.get_secret(provider_id))
        except VaultError:
            return False

    def set_json(self, token: str, namespace: str, key: str, value: Any) -> None:
        self.validate_session(token)
        if not namespace or not key:
            raise VaultError("Vault namespace and key are required.")
        self._write_record(f"json:{namespace}:{key}", value)

    def get_json(self, namespace: str, key: str) -> Any:
        return self._read_record(f"json:{namespace}:{key}")

    def rotate_data_key(self, token: str) -> int:
        self.validate_session(token)
        with self._lock:
            if self._root_key is None:
                raise VaultError("Vault is locked.")
            old_keys = dict(self._data_keys)
            new_id = max(self._data_keys.keys(), default=0) + 1
            self._data_keys[new_id] = bytearray(os.urandom(32))
            self._active_data_key_id = new_id
            records = self._read_records()
            clear_records: list[tuple[str, str | None, Any]] = []
            for record_id, envelope in list(records["records"].items()):
                clear_records.append(
                    (record_id, envelope.get("label"), self._decrypt_record(record_id, envelope))
                )
            records["records"] = {}
            for record_id, label, clear in clear_records:
                envelope = self._encrypt_record(record_id, clear)
                if label:
                    envelope["label"] = label
                records["records"][record_id] = envelope
            self._atomic_json(self.records_path, records)
            for key_id, key in old_keys.items():
                if key_id != new_id:
                    self._zero(key)
                    self._data_keys.pop(key_id, None)
            self._persist_keyring()
            return new_id

    def import_environment_keys(self, token: str) -> list[str]:
        self.validate_session(token)
        if not SETTINGS.allow_env_key_import:
            raise VaultError("Environment-key import is disabled by policy.")
        mapping = {
            "openai": "OPENAI_API_KEY",
            "xai": "XAI_API_KEY",
            "digitalocean": "DIGITALOCEAN_TOKEN",
            "gemini": "GEMINI_API_KEY",
        }
        imported: list[str] = []
        for provider, variable in mapping.items():
            value = os.environ.get(variable)
            if value:
                self.set_secret(token, provider, value)
                imported.append(provider)
        return imported

    def _list_provider_ids(self) -> list[str]:
        records = self._read_records()["records"]
        providers: list[str] = []
        for envelope in records.values():
            label = envelope.get("label")
            if isinstance(label, str) and label.startswith("provider:"):
                providers.append(label.split(":", 1)[1])
        return providers

    def _write_record(self, label: str, value: Any) -> None:
        with self._lock:
            record_id = self._record_id(label)
            records = self._read_records()
            envelope = self._encrypt_record(record_id, value)
            envelope["label"] = label
            records["records"][record_id] = envelope
            self._atomic_json(self.records_path, records)

    def _read_record(self, label: str) -> Any:
        with self._lock:
            record_id = self._record_id(label)
            records = self._read_records()
            envelope = records["records"].get(record_id)
            if envelope is None:
                return None
            return self._decrypt_record(record_id, envelope)

    def _delete_record(self, label: str) -> None:
        with self._lock:
            record_id = self._record_id(label)
            records = self._read_records()
            records["records"].pop(record_id, None)
            self._atomic_json(self.records_path, records)

    def _record_id(self, label: str) -> str:
        if self._index_key is None:
            raise VaultError("Vault is locked.")
        return hashlib.blake2b(
            label.encode("utf-8"),
            key=bytes(self._index_key),
            digest_size=24,
        ).hexdigest()

    def _encrypt_record(self, record_id: str, value: Any) -> dict[str, Any]:
        if self._active_data_key_id is None:
            raise VaultError("Vault is locked.")
        key = self._data_keys[self._active_data_key_id]
        clear = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        aad = f"{VAULT_FORMAT}:{record_id}:{self._active_data_key_id}".encode()
        return {
            "keyId": self._active_data_key_id,
            **aes_gcm_encrypt(clear, bytes(key), aad),
        }

    def _decrypt_record(self, record_id: str, envelope: dict[str, Any]) -> Any:
        key_id = int(envelope["keyId"])
        key = self._data_keys.get(key_id)
        if key is None:
            raise VaultError("Vault record references an unavailable data key.")
        aad = f"{VAULT_FORMAT}:{record_id}:{key_id}".encode()
        try:
            clear = aes_gcm_decrypt(envelope, bytes(key), aad)
            return json.loads(clear.decode("utf-8"))
        except (CryptoError, json.JSONDecodeError) as exc:
            raise VaultError("Vault record failed authentication.") from exc

    def _install_root_key(self, root_key: bytes) -> None:
        if len(root_key) != 32:
            raise VaultError("Vault root key is malformed.")
        self.lock()
        self._root_key = bytearray(root_key)
        self._load_keyring()

    def _persist_keyring(self) -> None:
        if self._root_key is None or self._index_key is None or self._active_data_key_id is None:
            raise VaultError("Vault keyring cannot be persisted while locked.")
        clear = json.dumps(
            {
                "indexKey": base64.b64encode(self._index_key).decode(),
                "dataKeys": {
                    str(key_id): base64.b64encode(key).decode()
                    for key_id, key in self._data_keys.items()
                },
                "activeDataKeyId": self._active_data_key_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope = {
            "format": VAULT_FORMAT,
            **aes_gcm_encrypt(
                clear,
                bytes(self._root_key),
                f"{VAULT_FORMAT}:keyring".encode(),
            ),
        }
        self._atomic_json(self.keyring_path, envelope)

    def _load_keyring(self) -> None:
        if self._root_key is None:
            raise VaultError("Vault is locked.")
        try:
            envelope = json.loads(self.keyring_path.read_text())
            clear = aes_gcm_decrypt(
                envelope,
                bytes(self._root_key),
                f"{VAULT_FORMAT}:keyring".encode(),
            )
            payload = json.loads(clear.decode("utf-8"))
            index_key = base64.b64decode(payload["indexKey"])
            data_keys = {
                int(key_id): bytearray(base64.b64decode(value))
                for key_id, value in dict(payload["dataKeys"]).items()
            }
            active_id = int(payload["activeDataKeyId"])
            if len(index_key) != 32 or active_id not in data_keys:
                raise ValueError("invalid keyring")
        except Exception as exc:
            self.lock()
            raise VaultError("Vault keyring failed authentication.") from exc
        self._index_key = bytearray(index_key)
        self._data_keys = data_keys
        self._active_data_key_id = active_id

    def _new_session(self) -> str:
        token = secrets.token_urlsafe(48)
        self._sessions[token] = time.time() + SETTINGS.session_ttl_seconds
        return token

    def _live_sessions(self) -> dict[str, float]:
        now = time.time()
        self._sessions = {token: expiry for token, expiry in self._sessions.items() if expiry > now}
        return dict(self._sessions)

    def _read_header_optional(self) -> Optional[dict[str, Any]]:
        if not self.header_path.exists():
            return None
        return self._read_header()

    def _read_header(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.header_path.read_text())
            if payload.get("format") != VAULT_FORMAT:
                raise ValueError("unsupported format")
            return payload
        except Exception as exc:
            raise VaultError("Vault header is missing or malformed.") from exc

    def _read_records(self) -> dict[str, Any]:
        if not self.records_path.exists():
            return {"format": VAULT_FORMAT, "records": {}}
        try:
            payload = json.loads(self.records_path.read_text())
            if payload.get("format") != VAULT_FORMAT or not isinstance(payload.get("records"), dict):
                raise ValueError("unsupported records")
            return payload
        except Exception as exc:
            raise VaultError("Vault records are malformed.") from exc

    def _atomic_json(self, path: Path, payload: Any) -> None:
        temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True))
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.replace(path)

    @staticmethod
    def _normalize_provider(provider_id: str) -> str:
        normalized = provider_id.strip().lower().replace("_", "-")
        allowed = {"openai", "xai", "digitalocean", "gemini"}
        if normalized not in allowed:
            raise VaultError(f"Unsupported provider id: {provider_id}")
        return normalized

    @staticmethod
    def _zero(value: Optional[bytearray]) -> None:
        if value is None:
            return
        for index in range(len(value)):
            value[index] = 0


VAULT = SecureVault()
