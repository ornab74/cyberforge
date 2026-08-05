from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional
import base64
import hashlib
import hmac
import importlib
import importlib.util
import json
import os
import tempfile

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

AES_STREAM_MAGIC = b"CYBERFORGE-AES-GCM-STREAM-v1\n"
PQ_STREAM_MAGIC = b"CYBERFORGE-MLKEM-X25519-STREAM-v1\n"
PQ_BUNDLE_FORMAT = "cyberforge-pq-recovery-v1"
GCM_NONCE_BYTES = 12
GCM_TAG_BYTES = 16
DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024
MAX_HEADER_BYTES = 1024 * 1024


class CryptoError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArgonPolicy:
    memory_kib: int = 64 * 1024
    iterations: int = 3
    parallelism: int = 1
    salt_bytes: int = 32


@dataclass(frozen=True)
class RecoveryIdentity:
    public_json: str
    encrypted_private_json: str
    fingerprint: str
    suite: str


def _b64e(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64d(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), validate=True)


def derive_password_key(password: str, salt: bytes, policy: ArgonPolicy) -> bytes:
    if len(password) < 12:
        raise CryptoError("Vault password must contain at least 12 characters.")
    if not (8 * 1024 <= policy.memory_kib <= 256 * 1024):
        raise CryptoError("Argon2 memory policy is outside the supported range.")
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=policy.iterations,
        memory_cost=policy.memory_kib,
        parallelism=policy.parallelism,
        hash_len=32,
        type=Type.ID,
        version=19,
    )


def aes_gcm_encrypt(clear: bytes, key: bytes, aad: bytes = b"") -> dict[str, str]:
    if len(key) != 32:
        raise CryptoError("AES-256-GCM requires a 32-byte key.")
    nonce = os.urandom(GCM_NONCE_BYTES)
    sealed = AESGCM(key).encrypt(nonce, clear, aad)
    return {"nonce": _b64e(nonce), "ciphertext": _b64e(sealed)}


def aes_gcm_decrypt(envelope: dict[str, str], key: bytes, aad: bytes = b"") -> bytes:
    if len(key) != 32:
        raise CryptoError("AES-256-GCM requires a 32-byte key.")
    try:
        return AESGCM(key).decrypt(
            _b64d(envelope["nonce"]),
            _b64d(envelope["ciphertext"]),
            aad,
        )
    except Exception as exc:  # authentication failures are intentionally generic
        raise CryptoError("Encrypted material failed authentication.") from exc


def sha256_file(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def constant_time_equal(left: str | bytes, right: str | bytes) -> bool:
    left_bytes = left if isinstance(left, bytes) else left.encode("utf-8")
    right_bytes = right if isinstance(right, bytes) else right.encode("utf-8")
    return hmac.compare_digest(left_bytes, right_bytes)


def _atomic_path(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(handle)
    path = Path(name)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _encrypt_stream(
    source: Path,
    destination: Path,
    key: bytes,
    prefix: bytes,
    aad: bytes,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
) -> None:
    nonce = os.urandom(GCM_NONCE_BYTES)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(aad)
    temporary = _atomic_path(destination)
    try:
        with source.open("rb") as incoming, temporary.open("wb") as outgoing:
            outgoing.write(prefix)
            outgoing.write(nonce)
            for chunk in iter(lambda: incoming.read(chunk_bytes), b""):
                outgoing.write(encryptor.update(chunk))
            outgoing.write(encryptor.finalize())
            outgoing.write(encryptor.tag)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        temporary.replace(destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _decrypt_stream(
    source: Path,
    destination: Path,
    key: bytes,
    ciphertext_offset: int,
    nonce: bytes,
    aad: bytes,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
) -> None:
    size = source.stat().st_size
    ciphertext_bytes = size - ciphertext_offset - GCM_TAG_BYTES
    if ciphertext_bytes < 0:
        raise CryptoError("Encrypted stream is truncated.")
    with source.open("rb") as incoming:
        incoming.seek(size - GCM_TAG_BYTES)
        tag = incoming.read(GCM_TAG_BYTES)
    decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
    decryptor.authenticate_additional_data(aad)
    temporary = _atomic_path(destination)
    try:
        with source.open("rb") as incoming, temporary.open("wb") as outgoing:
            incoming.seek(ciphertext_offset)
            remaining = ciphertext_bytes
            while remaining:
                chunk = incoming.read(min(chunk_bytes, remaining))
                if not chunk:
                    raise CryptoError("Encrypted stream ended unexpectedly.")
                outgoing.write(decryptor.update(chunk))
                remaining -= len(chunk)
            outgoing.write(decryptor.finalize())
            outgoing.flush()
            os.fsync(outgoing.fileno())
        temporary.replace(destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, CryptoError):
            raise
        raise CryptoError("Encrypted stream failed authentication.") from exc


def encrypt_file_aes_gcm(source: Path, destination: Path, key: bytes) -> None:
    _encrypt_stream(source, destination, key, AES_STREAM_MAGIC, AES_STREAM_MAGIC)


def decrypt_file_aes_gcm(source: Path, destination: Path, key: bytes) -> None:
    with source.open("rb") as handle:
        magic = handle.read(len(AES_STREAM_MAGIC))
        if magic != AES_STREAM_MAGIC:
            raise CryptoError("Not a CyberForge AES-GCM stream.")
        nonce = handle.read(GCM_NONCE_BYTES)
    _decrypt_stream(
        source,
        destination,
        key,
        len(AES_STREAM_MAGIC) + GCM_NONCE_BYTES,
        nonce,
        AES_STREAM_MAGIC,
    )


def oqs_available() -> bool:
    return importlib.util.find_spec("oqs") is not None


def _oqs_module():
    if not oqs_available():
        return None
    try:
        return importlib.import_module("oqs")
    except Exception:
        return None


def _select_mlkem(oqs_mod) -> Optional[str]:
    candidates = ("ML-KEM-1024", "ML-KEM-768", "Kyber1024", "Kyber768")
    try:
        enabled = set(oqs_mod.get_enabled_kem_mechanisms())
    except Exception:
        enabled = set()
    for candidate in candidates:
        if enabled and candidate not in enabled:
            continue
        try:
            with oqs_mod.KeyEncapsulation(candidate):
                return candidate
        except Exception:
            continue
    return None


def pq_status() -> dict[str, object]:
    oqs_mod = _oqs_module()
    algorithm = _select_mlkem(oqs_mod) if oqs_mod is not None else None
    return {
        "available": algorithm is not None,
        "algorithm": algorithm,
        "suite": (
            f"{algorithm}+X25519+HKDF-SHA512+AES-256-GCM"
            if algorithm
            else "AES-256-GCM (ML-KEM optional dependency unavailable)"
        ),
    }


def generate_recovery_identity(password: str, policy: ArgonPolicy = ArgonPolicy()) -> RecoveryIdentity:
    oqs_mod = _oqs_module()
    algorithm = _select_mlkem(oqs_mod) if oqs_mod is not None else None
    if algorithm is None:
        raise CryptoError("Install liboqs-python to create a post-quantum recovery identity.")

    with oqs_mod.KeyEncapsulation(algorithm) as kem:
        mlkem_public = bytes(kem.generate_keypair())
        mlkem_private = bytes(kem.export_secret_key())
    x_private = X25519PrivateKey.generate()
    x_public = x_private.public_key()
    x_private_raw = x_private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    x_public_raw = x_public.public_bytes(Encoding.Raw, PublicFormat.Raw)

    public_map: dict[str, object] = {
        "format": PQ_BUNDLE_FORMAT,
        "suite": f"{algorithm}+X25519+HKDF-SHA512+AES-256-GCM",
        "mlKemAlgorithm": algorithm,
        "mlKemPublicKey": _b64e(mlkem_public),
        "x25519PublicKey": _b64e(x_public_raw),
        "createdAtUnix": int(__import__("time").time()),
    }
    canonical_public = json.dumps(public_map, sort_keys=True, separators=(",", ":")).encode()
    fingerprint = hashlib.sha3_256(canonical_public).hexdigest()
    public_map["fingerprint"] = fingerprint

    salt = os.urandom(policy.salt_bytes)
    password_key = derive_password_key(password, salt, policy)
    private_clear = len(mlkem_private).to_bytes(4, "big") + mlkem_private + x_private_raw
    aad = json.dumps(public_map, sort_keys=True, separators=(",", ":")).encode()
    wrapped = aes_gcm_encrypt(private_clear, password_key, aad)
    private_map = {
        "format": PQ_BUNDLE_FORMAT,
        "public": public_map,
        "kdf": {
            "algorithm": "Argon2id-1.3",
            "salt": _b64e(salt),
            "memoryKiB": policy.memory_kib,
            "iterations": policy.iterations,
            "parallelism": policy.parallelism,
        },
        "wrappedPrivate": wrapped,
    }
    return RecoveryIdentity(
        public_json=json.dumps(public_map, indent=2, sort_keys=True),
        encrypted_private_json=json.dumps(private_map, indent=2, sort_keys=True),
        fingerprint=fingerprint,
        suite=str(public_map["suite"]),
    )


def _unlock_recovery_private(private_json: str, password: str) -> tuple[dict, bytes, bytes]:
    try:
        envelope = json.loads(private_json)
        public = dict(envelope["public"])
        kdf = dict(envelope["kdf"])
        policy = ArgonPolicy(
            memory_kib=int(kdf["memoryKiB"]),
            iterations=int(kdf["iterations"]),
            parallelism=int(kdf["parallelism"]),
            salt_bytes=len(_b64d(kdf["salt"])),
        )
        password_key = derive_password_key(password, _b64d(kdf["salt"]), policy)
        aad = json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
        clear = aes_gcm_decrypt(dict(envelope["wrappedPrivate"]), password_key, aad)
        mlkem_len = int.from_bytes(clear[:4], "big")
        mlkem_private = clear[4 : 4 + mlkem_len]
        x_private = clear[4 + mlkem_len :]
        if len(x_private) != 32:
            raise CryptoError("Recovery private key is malformed.")
        return public, mlkem_private, x_private
    except CryptoError:
        raise
    except Exception as exc:
        raise CryptoError("Recovery identity is malformed or cannot be unlocked.") from exc


def pq_encrypt_bytes(clear: bytes, public_json: str) -> bytes:
    oqs_mod = _oqs_module()
    if oqs_mod is None:
        raise CryptoError("liboqs-python is required for ML-KEM encryption.")
    try:
        public = json.loads(public_json)
        algorithm = str(public["mlKemAlgorithm"])
        mlkem_public = _b64d(public["mlKemPublicKey"])
        x_public = X25519PublicKey.from_public_bytes(_b64d(public["x25519PublicKey"]))
        with oqs_mod.KeyEncapsulation(algorithm) as kem:
            kem_ciphertext, kem_shared = kem.encap_secret(mlkem_public)
        ephemeral = X25519PrivateKey.generate()
        classical_shared = ephemeral.exchange(x_public)
        ephemeral_public = ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        salt = os.urandom(32)
        header = {
            "format": "cyberforge-pq-envelope-v1",
            "suite": public["suite"],
            "recipientFingerprint": public["fingerprint"],
            "mlKemCiphertext": _b64e(bytes(kem_ciphertext)),
            "ephemeralX25519PublicKey": _b64e(ephemeral_public),
            "salt": _b64e(salt),
        }
        aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        key = HKDF(
            algorithm=hashes.SHA512(),
            length=32,
            salt=salt,
            info=b"CyberForge/PQEnvelope/v1" + aad,
        ).derive(bytes(kem_shared) + classical_shared)
        header["sealed"] = aes_gcm_encrypt(clear, key, aad)
        return json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    except CryptoError:
        raise
    except Exception as exc:
        raise CryptoError("Unable to create post-quantum envelope.") from exc


def pq_decrypt_bytes(envelope_bytes: bytes, private_json: str, password: str) -> bytes:
    oqs_mod = _oqs_module()
    if oqs_mod is None:
        raise CryptoError("liboqs-python is required for ML-KEM decryption.")
    public, mlkem_private, x_private_raw = _unlock_recovery_private(private_json, password)
    try:
        envelope = json.loads(envelope_bytes.decode("utf-8"))
        if envelope["recipientFingerprint"] != public["fingerprint"]:
            raise CryptoError("Post-quantum envelope belongs to another recovery identity.")
        algorithm = str(public["mlKemAlgorithm"])
        with oqs_mod.KeyEncapsulation(algorithm, mlkem_private) as kem:
            kem_shared = kem.decap_secret(_b64d(envelope["mlKemCiphertext"]))
        x_private = X25519PrivateKey.from_private_bytes(x_private_raw)
        classical_shared = x_private.exchange(
            X25519PublicKey.from_public_bytes(_b64d(envelope["ephemeralX25519PublicKey"]))
        )
        salt = _b64d(envelope["salt"])
        header = {key: value for key, value in envelope.items() if key != "sealed"}
        aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        key = HKDF(
            algorithm=hashes.SHA512(),
            length=32,
            salt=salt,
            info=b"CyberForge/PQEnvelope/v1" + aad,
        ).derive(bytes(kem_shared) + classical_shared)
        return aes_gcm_decrypt(dict(envelope["sealed"]), key, aad)
    except CryptoError:
        raise
    except Exception as exc:
        raise CryptoError("Post-quantum envelope failed authentication.") from exc
