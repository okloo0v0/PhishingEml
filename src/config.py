import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_env: str = "dev"
    database_url: str = "sqlite:///./data/phishing.db"
    model_dir: Path = PROJECT_ROOT / "models"
    sample_dir: Path = PROJECT_ROOT / "data" / "samples"
    max_upload_bytes: int = 5 * 1024 * 1024
    max_body_chars: int = 200_000
    log_level: str = "INFO"
    allow_network: bool = False
    # 基础版不实现沙箱隔离，网络访问能力作为后续隔离沙箱扩展保留。


def get_settings() -> Settings:
    allow_network = os.getenv("ALLOW_NETWORK", "false").lower() == "true"
    if allow_network:
        raise ValueError(
            "ALLOW_NETWORK=true is reserved for a future isolated sandbox "
            "and is not supported by the basic version"
        )

    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite:///./data/phishing.db",
        ),
        model_dir=Path(os.getenv("MODEL_DIR", str(PROJECT_ROOT / "models"))),
        sample_dir=Path(
            os.getenv("SAMPLE_DIR", str(PROJECT_ROOT / "data" / "samples"))
        ),
        max_upload_bytes=int(
            os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))
        ),
        max_body_chars=int(os.getenv("MAX_BODY_CHARS", "200000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        allow_network=False,
    )

