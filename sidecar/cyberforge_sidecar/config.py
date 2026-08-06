from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


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
    allow_env_key_import: bool = _bool_env("CYBERFORGE_ALLOW_ENV_KEY_IMPORT", False)
    require_authorization: bool = _bool_env("CYBERFORGE_REQUIRE_AUTHORIZATION", True)

    # Encrypted SQLite system of record.
    storage_db_name: str = os.environ.get("CYBERFORGE_STORAGE_DB", "cyberforge.sqlite3")
    auto_persist_research: bool = _bool_env("CYBERFORGE_AUTO_PERSIST_RESEARCH", True)

    # Weaviate routing: auto -> remote, then embedded, then encrypted SQLite only.
    weaviate_mode: str = os.environ.get("CYBERFORGE_WEAVIATE_MODE", "auto").strip().lower()
    weaviate_http_host: str = os.environ.get("CYBERFORGE_WEAVIATE_HTTP_HOST", "127.0.0.1")
    weaviate_http_port: int = int(os.environ.get("CYBERFORGE_WEAVIATE_HTTP_PORT", "8080"))
    weaviate_grpc_host: str = os.environ.get("CYBERFORGE_WEAVIATE_GRPC_HOST", "127.0.0.1")
    weaviate_grpc_port: int = int(os.environ.get("CYBERFORGE_WEAVIATE_GRPC_PORT", "50051"))
    weaviate_secure: bool = _bool_env("CYBERFORGE_WEAVIATE_SECURE", False)
    weaviate_api_key: str = os.environ.get("CYBERFORGE_WEAVIATE_API_KEY", "")
    weaviate_collection: str = os.environ.get(
        "CYBERFORGE_WEAVIATE_COLLECTION", "CyberForgeMemoryV1"
    )
    weaviate_embedded_version: str = os.environ.get(
        "CYBERFORGE_WEAVIATE_EMBEDDED_VERSION", "1.37.0"
    )
    weaviate_embedded_http_port: int = int(
        os.environ.get("CYBERFORGE_WEAVIATE_EMBEDDED_HTTP_PORT", "8079")
    )
    weaviate_embedded_grpc_port: int = int(
        os.environ.get("CYBERFORGE_WEAVIATE_EMBEDDED_GRPC_PORT", "50050")
    )
    weaviate_embedded_log_level: str = os.environ.get(
        "CYBERFORGE_WEAVIATE_EMBEDDED_LOG_LEVEL", "error"
    )
    weaviate_hybrid_alpha: float = float(
        os.environ.get("CYBERFORGE_WEAVIATE_HYBRID_ALPHA", "0.55")
    )
    memory_rrf_k: int = int(os.environ.get("CYBERFORGE_MEMORY_RRF_K", "60"))
    memory_mmr_lambda: float = float(
        os.environ.get("CYBERFORGE_MEMORY_MMR_LAMBDA", "0.72")
    )

    @property
    def vault_dir(self) -> Path:
        return self.data_dir / "vault"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "storage"

    @property
    def storage_db(self) -> Path:
        return self.storage_dir / self.storage_db_name

    @property
    def weaviate_dir(self) -> Path:
        return self.data_dir / "weaviate"

    @property
    def weaviate_embedded_data_path(self) -> Path:
        return self.weaviate_dir / "data"

    @property
    def weaviate_embedded_binary_path(self) -> Path:
        return self.weaviate_dir / "bin"


SETTINGS = Settings()


def ensure_directories() -> None:
    for path in (
        SETTINGS.data_dir,
        SETTINGS.vault_dir,
        SETTINGS.models_dir,
        SETTINGS.reports_dir,
        SETTINGS.storage_dir,
        SETTINGS.weaviate_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except OSError:
            pass
