from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
import json
import os
import secrets

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import SETTINGS, ensure_directories
from .crypto import (
    CryptoError,
    generate_recovery_identity,
    pq_decrypt_bytes,
    pq_encrypt_bytes,
    pq_status,
)
from .models import MODEL_MANAGER, ModelError
from .news import capture_news
from .providers import MODEL_COUNCIL
from .scanner import SUPER_SCANNER, ScannerError, default_packet
from .simcom import SIMCOM
from .vault import VAULT, VaultError


class PasswordRequest(BaseModel):
    password: str = Field(min_length=12, max_length=1024)
    password_required: bool = True


class ProviderSecretRequest(BaseModel):
    provider: str
    secret: str = Field(min_length=1, max_length=65536)


class ModelActionRequest(BaseModel):
    profile_id: str


class LocalModelImportRequest(ModelActionRequest):
    source_path: str = Field(min_length=1, max_length=4096)


class SimComRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4096)
    packet: Optional[dict[str, Any]] = None


class NewsCaptureRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    provider: str = Field(default="xai")


class RecoveryRequest(BaseModel):
    password: str = Field(min_length=12, max_length=1024)


class PqEncryptRequest(BaseModel):
    public_key_json: str
    payload_base64: str


class PqDecryptRequest(BaseModel):
    encrypted_private_key_json: str
    password: str
    envelope_base64: str


def _token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Vault session bearer token required.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        VAULT.validate_session(token)
    except VaultError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return token


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    if SETTINGS.bind_host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get(
        "CYBERFORGE_ALLOW_REMOTE_BIND", "false"
    ).lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            "CyberForge refuses non-loopback binding unless CYBERFORGE_ALLOW_REMOTE_BIND=true."
        )
    yield
    MODEL_MANAGER.unload_all()
    VAULT.lock()


app = FastAPI(
    title="CyberForge Local Sidecar",
    version=__version__,
    description="Local-first white-hat security simulation, model orchestration, and encrypted provider vault.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_size_boundary(request: Request, call_next):
    content_length = int(request.headers.get("content-length") or 0)
    if content_length > SETTINGS.max_request_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request exceeds local policy limit."})
    return await call_next(request)


@app.exception_handler(VaultError)
async def vault_error(_: Request, exc: VaultError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ModelError)
async def model_error(_: Request, exc: ModelError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ScannerError)
async def scanner_error(_: Request, exc: ScannerError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, Any]:
    vault = VAULT.status()
    return {
        "status": "ok",
        "version": __version__,
        "bind": SETTINGS.bind_host,
        "defenseOnly": True,
        "vault": {
            "exists": vault.exists,
            "unlocked": vault.unlocked,
            "providers": list(vault.provider_ids),
            "activeDataKeyId": vault.active_data_key_id,
        },
        "postQuantum": pq_status(),
        "models": [status.__dict__ for status in MODEL_MANAGER.statuses()],
        "council": MODEL_COUNCIL.status(),
    }


@app.get("/v1/scenarios/default")
async def default_scenario() -> dict[str, Any]:
    return default_packet()


@app.post("/v1/scan")
async def scan(
    request: Request,
    packet: dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    if bool(packet.get("includeRemoteModels", False)):
        _token(authorization)
    return await SUPER_SCANNER.scan(packet)


@app.post("/v1/simcom")
async def simcom(body: SimComRequest) -> dict[str, Any]:
    return (await SIMCOM.execute(body.command, packet=body.packet)).to_dict()


@app.post("/v1/news/capture")
async def news_capture(body: NewsCaptureRequest, _: str = Depends(_token)) -> dict[str, Any]:
    return await capture_news(body.query, body.provider)


@app.get("/v1/vault/status")
async def vault_status() -> dict[str, Any]:
    status = VAULT.status()
    return {
        "exists": status.exists,
        "unlocked": status.unlocked,
        "sessionCount": status.session_count,
        "providers": list(status.provider_ids),
        "passwordRequired": status.password_required,
        "activeDataKeyId": status.active_data_key_id,
    }


@app.post("/v1/vault/create")
async def vault_create(body: PasswordRequest) -> dict[str, Any]:
    token = VAULT.create(body.password, password_required=body.password_required)
    return {"sessionToken": token, "expiresIn": SETTINGS.session_ttl_seconds}


@app.post("/v1/vault/unlock")
async def vault_unlock(body: PasswordRequest) -> dict[str, Any]:
    token = VAULT.unlock(body.password)
    return {"sessionToken": token, "expiresIn": SETTINGS.session_ttl_seconds}


@app.post("/v1/vault/unlock-device")
async def vault_unlock_device() -> dict[str, Any]:
    token = VAULT.unlock_with_device_key()
    return {"sessionToken": token, "expiresIn": SETTINGS.session_ttl_seconds}


@app.post("/v1/vault/lock")
async def vault_lock(_: str = Depends(_token)) -> dict[str, bool]:
    VAULT.lock()
    return {"locked": True}


@app.post("/v1/vault/providers")
async def vault_provider(body: ProviderSecretRequest, token: str = Depends(_token)) -> dict[str, Any]:
    VAULT.set_secret(token, body.provider, body.secret)
    return {"provider": body.provider, "configured": True}


@app.delete("/v1/vault/providers/{provider}")
async def vault_provider_delete(provider: str, token: str = Depends(_token)) -> dict[str, Any]:
    VAULT.delete_secret(token, provider)
    return {"provider": provider, "configured": False}


@app.post("/v1/vault/rotate")
async def vault_rotate(token: str = Depends(_token)) -> dict[str, Any]:
    return {"activeDataKeyId": VAULT.rotate_data_key(token)}


@app.post("/v1/vault/import-environment")
async def vault_import_environment(token: str = Depends(_token)) -> dict[str, Any]:
    return {"imported": VAULT.import_environment_keys(token)}


@app.get("/v1/models")
async def models() -> dict[str, Any]:
    return {"models": [status.__dict__ for status in MODEL_MANAGER.statuses()]}


@app.post("/v1/models/install")
async def model_install(body: ModelActionRequest, token: str = Depends(_token)) -> dict[str, Any]:
    status = await MODEL_MANAGER.install(body.profile_id, session_token=token)
    return status.__dict__


@app.post("/v1/models/import")
async def model_import(body: LocalModelImportRequest, token: str = Depends(_token)) -> dict[str, Any]:
    return MODEL_MANAGER.import_local(body.profile_id, body.source_path, session_token=token).__dict__


@app.post("/v1/models/load")
async def model_load(body: ModelActionRequest, token: str = Depends(_token)) -> dict[str, Any]:
    return MODEL_MANAGER.load(body.profile_id, session_token=token).__dict__


@app.post("/v1/models/unload")
async def model_unload(body: ModelActionRequest, _: str = Depends(_token)) -> dict[str, Any]:
    MODEL_MANAGER.unload(body.profile_id)
    return MODEL_MANAGER.status(body.profile_id).__dict__


@app.get("/v1/crypto/pq-status")
async def post_quantum_status() -> dict[str, Any]:
    return pq_status()


@app.post("/v1/crypto/recovery-identity")
async def recovery_identity(body: RecoveryRequest, _: str = Depends(_token)) -> dict[str, Any]:
    try:
        identity = generate_recovery_identity(body.password)
        return {
            "publicKeyJson": identity.public_json,
            "encryptedPrivateKeyJson": identity.encrypted_private_json,
            "fingerprint": identity.fingerprint,
            "suite": identity.suite,
        }
    except CryptoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/crypto/pq-encrypt")
async def pq_encrypt(body: PqEncryptRequest, _: str = Depends(_token)) -> dict[str, Any]:
    try:
        import base64

        envelope = pq_encrypt_bytes(base64.b64decode(body.payload_base64), body.public_key_json)
        return {"envelopeBase64": base64.b64encode(envelope).decode("ascii")}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/crypto/pq-decrypt")
async def pq_decrypt(body: PqDecryptRequest, _: str = Depends(_token)) -> dict[str, Any]:
    try:
        import base64

        clear = pq_decrypt_bytes(
            base64.b64decode(body.envelope_base64),
            body.encrypted_private_key_json,
            body.password,
        )
        return {"payloadBase64": base64.b64encode(clear).decode("ascii")}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
