from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Optional
import base64
import hashlib
import importlib
import importlib.util
import os
import tempfile
import shutil

import httpx

from .config import MODEL_PROFILES, ModelProfile, SETTINGS, ensure_directories
from .crypto import (
    CryptoError,
    constant_time_equal,
    decrypt_file_aes_gcm,
    encrypt_file_aes_gcm,
    sha256_file,
)
from .vault import VAULT, VaultError


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelStatus:
    id: str
    name: str
    runtime: str
    installed: bool
    loaded: bool
    encrypted_at_rest: bool
    path: str
    expected_sha256: str
    actual_sha256: str | None
    error: str | None = None


class LocalModelRuntime:
    def __init__(self, profile: ModelProfile, clear_model_path: Path) -> None:
        self.profile = profile
        self.clear_model_path = clear_model_path
        self.runtime = profile.runtime
        self._engine_context: Any = None
        self._engine: Any = None
        self._conversation_context: Any = None
        self._conversation: Any = None
        self._llama: Any = None
        self._lock = RLock()

    def load(self) -> "LocalModelRuntime":
        with self._lock:
            if self.runtime == "litert_lm":
                if importlib.util.find_spec("litert_lm") is None:
                    raise ModelError(
                        "LiteRT-LM runtime missing. Install litert-lm==0.11.0."
                    )
                litert_lm = importlib.import_module("litert_lm")
                try:
                    litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)
                except Exception:
                    pass
                self._engine_context = litert_lm.Engine(str(self.clear_model_path))
                self._engine = (
                    self._engine_context.__enter__()
                    if hasattr(self._engine_context, "__enter__")
                    else self._engine_context
                )
                self._conversation_context = self._engine.create_conversation()
                self._conversation = (
                    self._conversation_context.__enter__()
                    if hasattr(self._conversation_context, "__enter__")
                    else self._conversation_context
                )
                return self

            if importlib.util.find_spec("llama_cpp") is None:
                raise ModelError(
                    "llama-cpp-python is missing. Install the sidecar local-model extra."
                )
            llama_cpp = importlib.import_module("llama_cpp")
            self._llama = llama_cpp.Llama(
                model_path=str(self.clear_model_path),
                n_ctx=self.profile.context_tokens,
                n_threads=max(2, min(8, os.cpu_count() or 4)),
                n_batch=256,
                verbose=False,
            )
            return self

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: Optional[int] = None,
        temperature: float = 0.15,
        json_mode: bool = False,
    ) -> str:
        with self._lock:
            max_tokens = max_tokens or self.profile.default_max_tokens
            if self.runtime == "litert_lm":
                if self._conversation is None:
                    raise ModelError("Gemma LiteRT-LM runtime is not loaded.")
                response = self._conversation.send_message(prompt)
                return self._extract_litert(response)
            if self._llama is None:
                raise ModelError("Llama runtime is not loaded.")
            kwargs: dict[str, Any] = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "repeat_penalty": 1.08,
                "stop": ["</scan>", "<|eot_id|>"],
            }
            if json_mode:
                try:
                    kwargs["response_format"] = {"type": "json_object"}
                except Exception:
                    pass
            output = self._llama(**kwargs)
            choices = output.get("choices", []) if isinstance(output, dict) else []
            if choices and isinstance(choices[0], dict):
                return str(choices[0].get("text", "")).strip()
            return str(output)

    def close(self) -> None:
        with self._lock:
            for context in (self._conversation_context, self._engine_context):
                try:
                    exit_fn = getattr(context, "__exit__", None)
                    if callable(exit_fn):
                        exit_fn(None, None, None)
                except Exception:
                    pass
            self._conversation = None
            self._engine = None
            self._llama = None

    @staticmethod
    def _extract_litert(response: Any) -> str:
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            content = response.get("content")
            if isinstance(content, list):
                text = "".join(
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, dict)
                )
                if text:
                    return text.strip()
            return str(response.get("text", "")).strip()
        return str(response).strip()


class ModelManager:
    def __init__(self) -> None:
        ensure_directories()
        self._lock = RLock()
        self._runtimes: dict[str, LocalModelRuntime] = {}
        self._clear_paths: dict[str, Path] = {}

    def encrypted_path(self, profile: ModelProfile) -> Path:
        return SETTINGS.models_dir / f"{profile.filename}.cfgm"

    def metadata_path(self, profile: ModelProfile) -> Path:
        return SETTINGS.models_dir / f"{profile.filename}.metadata.json"

    def statuses(self) -> list[ModelStatus]:
        statuses: list[ModelStatus] = []
        for profile in MODEL_PROFILES.values():
            encrypted = self.encrypted_path(profile)
            actual = None
            if self.metadata_path(profile).exists():
                try:
                    import json

                    actual = json.loads(self.metadata_path(profile).read_text()).get(
                        "plaintextSha256"
                    )
                except Exception:
                    actual = None
            statuses.append(
                ModelStatus(
                    id=profile.id,
                    name=profile.display_name,
                    runtime=profile.runtime,
                    installed=encrypted.exists(),
                    loaded=profile.id in self._runtimes,
                    encrypted_at_rest=encrypted.exists(),
                    path=str(encrypted),
                    expected_sha256=profile.sha256,
                    actual_sha256=actual,
                )
            )
        return statuses

    async def install(
        self,
        profile_id: str,
        *,
        session_token: str,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> ModelStatus:
        VAULT.validate_session(session_token)
        profile = self._profile(profile_id)
        model_key = self._model_key(session_token)
        fd, temporary_name = tempfile.mkstemp(prefix="cyberforge-model-", suffix=".download")
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            digest = hashlib.sha256()
            done = 0
            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                async with client.stream("GET", profile.url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("Content-Length") or 0)
                    with temporary.open("wb") as handle:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            handle.write(chunk)
                            digest.update(chunk)
                            done += len(chunk)
                            if progress:
                                progress(done, total)
                        handle.flush()
                        os.fsync(handle.fileno())
            actual = digest.hexdigest()
            if not constant_time_equal(actual.lower(), profile.sha256.lower()):
                raise ModelError(
                    f"Model SHA-256 mismatch: expected {profile.sha256}, got {actual}."
                )
            encrypt_file_aes_gcm(temporary, self.encrypted_path(profile), model_key)
            import json

            self.metadata_path(profile).write_text(
                json.dumps(
                    {
                        "profileId": profile.id,
                        "runtime": profile.runtime,
                        "plaintextSha256": actual,
                        "encryptedAtRest": True,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return self.status(profile_id)
        finally:
            temporary.unlink(missing_ok=True)

    def import_local(
        self, profile_id: str, source_path: str, *, session_token: str
    ) -> ModelStatus:
        """Verify and encrypt an existing local model; never trusts its filename."""
        VAULT.validate_session(session_token)
        profile = self._profile(profile_id)
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ModelError("Selected local model file does not exist.")
        if source.stat().st_size == 0:
            raise ModelError("Selected local model file is empty.")
        actual = sha256_file(source)
        if not constant_time_equal(actual.lower(), profile.sha256.lower()):
            raise ModelError(
                f"Local model SHA-256 mismatch: expected {profile.sha256}, got {actual}."
            )
        temporary = Path(tempfile.mkstemp(prefix="cyberforge-import-", suffix=".model")[1])
        try:
            shutil.copyfile(source, temporary)
            encrypt_file_aes_gcm(temporary, self.encrypted_path(profile), self._model_key(session_token))
            import json
            self.metadata_path(profile).write_text(json.dumps({
                "profileId": profile.id,
                "runtime": profile.runtime,
                "plaintextSha256": actual,
                "encryptedAtRest": True,
                "source": "local-import",
            }, indent=2, sort_keys=True))
            return self.status(profile_id)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, profile_id: str, *, session_token: str) -> ModelStatus:
        VAULT.validate_session(session_token)
        with self._lock:
            profile = self._profile(profile_id)
            if profile.id in self._runtimes:
                return self.status(profile_id)
            encrypted = self.encrypted_path(profile)
            if not encrypted.exists():
                raise ModelError(f"Model {profile.id} is not installed.")
            model_key = self._model_key(session_token)
            fd, clear_name = tempfile.mkstemp(
                prefix=f"cyberforge-{profile.id}-", suffix=Path(profile.filename).suffix
            )
            os.close(fd)
            clear_path = Path(clear_name)
            try:
                decrypt_file_aes_gcm(encrypted, clear_path, model_key)
                actual = sha256_file(clear_path)
                if not constant_time_equal(actual.lower(), profile.sha256.lower()):
                    raise ModelError("Decrypted model hash does not match its pinned profile.")
                runtime = LocalModelRuntime(profile, clear_path).load()
                self._runtimes[profile.id] = runtime
                self._clear_paths[profile.id] = clear_path
                return self.status(profile_id)
            except Exception:
                clear_path.unlink(missing_ok=True)
                raise

    def unload(self, profile_id: str) -> None:
        with self._lock:
            runtime = self._runtimes.pop(profile_id, None)
            if runtime:
                runtime.close()
            path = self._clear_paths.pop(profile_id, None)
            if path:
                try:
                    size = path.stat().st_size
                    with path.open("r+b") as handle:
                        remaining = min(size, 16 * 1024 * 1024)
                        while remaining:
                            block = os.urandom(min(1024 * 1024, remaining))
                            handle.write(block)
                            remaining -= len(block)
                        handle.flush()
                        os.fsync(handle.fileno())
                except Exception:
                    pass
                path.unlink(missing_ok=True)

    def unload_all(self) -> None:
        for profile_id in list(self._runtimes):
            self.unload(profile_id)

    def generate(
        self,
        profile_id: str,
        prompt: str,
        *,
        max_tokens: Optional[int] = None,
        temperature: float = 0.15,
        json_mode: bool = False,
    ) -> str:
        runtime = self._runtimes.get(profile_id)
        if runtime is None:
            raise ModelError(f"Model {profile_id} is not loaded.")
        return runtime.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )

    def status(self, profile_id: str) -> ModelStatus:
        profile = self._profile(profile_id)
        return next(status for status in self.statuses() if status.id == profile.id)

    def _model_key(self, session_token: str) -> bytes:
        try:
            encoded = VAULT.get_json("models", "at-rest-key")
            if not encoded:
                encoded = base64.b64encode(os.urandom(32)).decode("ascii")
                VAULT.set_json(session_token, "models", "at-rest-key", encoded)
            key = base64.b64decode(str(encoded))
            if len(key) != 32:
                raise ModelError("Stored model encryption key is malformed.")
            return key
        except VaultError as exc:
            raise ModelError("Unlock the vault before using encrypted local models.") from exc

    @staticmethod
    def _profile(profile_id: str) -> ModelProfile:
        try:
            return MODEL_PROFILES[profile_id]
        except KeyError as exc:
            raise ModelError(f"Unknown local model profile: {profile_id}") from exc


MODEL_MANAGER = ModelManager()
