from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class ModelProfile:
    id: str
    display_name: str
    runtime: str
    filename: str
    url: str
    sha256: str
    context_tokens: int
    default_max_tokens: int


GEMMA4_E2B = ModelProfile(
    id="gemma4-e2b-litert-4bit",
    display_name="Gemma 4 E2B LiteRT-LM 4-bit",
    runtime="litert_lm",
    filename="gemma-4-E2B-it.litertlm",
    url=(
        "https://huggingface.co/litert-community/"
        "gemma-4-E2B-it-litert-lm/resolve/"
        "7fa1d78473894f7e736a21d920c3aa80f950c0db/"
        "gemma-4-E2B-it.litertlm"
    ),
    sha256="ab7838cdfc8f77e54d8ca45eadceb20452d9f01e4bfade03e5dce27911b27e42",
    context_tokens=8192,
    default_max_tokens=1024,
)

LLAMA3_SMALL = ModelProfile(
    id="llama3-small-q3",
    display_name="Llama 3 Small Q3_K_M",
    runtime="llama_cpp",
    filename="llama3-small-Q3_K_M.gguf",
    url=(
        "https://huggingface.co/tensorblock/llama3-small-GGUF/resolve/main/"
        "llama3-small-Q3_K_M.gguf"
    ),
    sha256="8e4f4856fb84bafb895f1eb08e6c03e4be613ead2d942f91561aeac742a619aa",
    context_tokens=4096,
    default_max_tokens=512,
)

MODEL_PROFILES = {profile.id: profile for profile in (GEMMA4_E2B, LLAMA3_SMALL)}


@dataclass(frozen=True)
class Settings:
    bind_host: str = os.environ.get("CYBERFORGE_BIND", "127.0.0.1")
    port: int = int(os.environ.get("CYBERFORGE_PORT", "8788"))
    data_dir: Path = Path(
        os.environ.get(
            "CYBERFORGE_DATA_DIR",
            str(Path.home() / ".local" / "share" / "cyberforge"),
        )
    )
    max_request_bytes: int = int(
        os.environ.get("CYBERFORGE_MAX_REQUEST_BYTES", str(4 * 1024 * 1024))
    )
    max_surfaces: int = int(os.environ.get("CYBERFORGE_MAX_SURFACES", "1024"))
    default_worlds: int = int(os.environ.get("CYBERFORGE_DEFAULT_WORLDS", "12000"))
    max_worlds: int = int(os.environ.get("CYBERFORGE_MAX_WORLDS", "250000"))
    session_ttl_seconds: int = int(
        os.environ.get("CYBERFORGE_SESSION_TTL_SECONDS", "1800")
    )
    allow_env_key_import: bool = os.environ.get(
        "CYBERFORGE_ALLOW_ENV_KEY_IMPORT", "false"
    ).lower() in {"1", "true", "yes"}
    require_authorization: bool = os.environ.get(
        "CYBERFORGE_REQUIRE_AUTHORIZATION", "true"
    ).lower() not in {"0", "false", "no"}

    @property
    def vault_dir(self) -> Path:
        return self.data_dir / "vault"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"


SETTINGS = Settings()


def ensure_directories() -> None:
    for path in (
        SETTINGS.data_dir,
        SETTINGS.vault_dir,
        SETTINGS.models_dir,
        SETTINGS.reports_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except OSError:
            pass
