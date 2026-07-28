from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_prefix="YUANQI_",
        extra="ignore",
        case_sensitive=False,
    )

    java_base_url: AnyHttpUrl = "http://localhost:8080"  # type: ignore[assignment]
    checkpoint_db_path: Path = Path("./data/checkpoints.sqlite")
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    java_max_response_bytes: int = Field(default=12_000_000, ge=64_000, le=50_000_000)
    planner_api_url: AnyHttpUrl | None = None
    planner_api_key: SecretStr | None = None
    planner_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    planner_max_response_bytes: int = Field(default=1_000_000, ge=1_024, le=5_000_000)
    planner_ollama_url: AnyHttpUrl | None = None
    planner_ollama_model: str = Field(default="qwen3:8b", min_length=1, max_length=200)
    sandbox_image: str = "yuanqi-agent-sandbox:local"
    sandbox_timeout_seconds: int = Field(default=20, ge=1, le=120)
    sandbox_memory: str = "512m"
    sandbox_cpus: float = Field(default=1.0, gt=0, le=4)
    sandbox_max_pids: int = Field(default=64, ge=16, le=512)
    sandbox_max_output_bytes: int = Field(default=1_000_000, ge=1_024, le=10_000_000)
    graphrag_enabled: bool = False
    neo4j_uri: str = Field(default="neo4j://localhost:7687", min_length=1)
    neo4j_username: str = Field(default="neo4j", min_length=1)
    neo4j_password: str = Field(default="yuanqi-local", min_length=8)
    neo4j_database: str = Field(default="neo4j", min_length=1)
    qdrant_url: AnyHttpUrl = "http://localhost:6333"  # type: ignore[assignment]
    qdrant_api_key: str | None = None
    qdrant_collection: str = Field(default="yuanqi_knowledge", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    embedding_api_url: AnyHttpUrl | None = None
    embedding_api_key: SecretStr | None = None
    embedding_model: str = Field(default="enterprise-embedding", min_length=1, max_length=200)
    embedding_dimensions: int = Field(default=384, ge=64, le=4_096)
    graphrag_top_k: int = Field(default=8, ge=1, le=50)
    graphrag_rrf_k: int = Field(default=60, ge=1, le=1_000)
    graphrag_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    cors_allowed_origins: list[str] = ["http://localhost:5173"]


def get_settings() -> Settings:
    return Settings()
