"""Application settings and environment configuration."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5440, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="ai_companion", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5440/ai_companion",
        alias="DATABASE_URL",
    )

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    primary_llm_provider: Literal["local", "openai", "local_http"] = Field(
        default="local",
        alias="PRIMARY_LLM_PROVIDER",
    )
    assistant_provider: Literal["local", "openai"] = Field(
        default="local",
        alias="ASSISTANT_PROVIDER",
    )
    openai_chat_model: str = Field(
        default="gpt-4o-mini",
        alias="OPENAI_CHAT_MODEL",
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    openai_chat_timeout_seconds: float = Field(
        default=15.0,
        alias="OPENAI_CHAT_TIMEOUT_SECONDS",
        ge=1.0,
        le=120.0,
    )
    local_llm_base_url: str = Field(default="http://localhost:11434/v1", alias="LOCAL_LLM_BASE_URL")
    local_llm_api_key: str = Field(default="local-dev-key", alias="LOCAL_LLM_API_KEY")
    local_llm_chat_model: str = Field(
        default="llama3.1:8b",
        alias="LOCAL_LLM_CHAT_MODEL",
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    local_llm_chat_timeout_seconds: float = Field(
        default=20.0,
        alias="LOCAL_LLM_CHAT_TIMEOUT_SECONDS",
        ge=1.0,
        le=300.0,
    )
    local_llm_embedding_model: str = Field(
        default="nomic-embed-text",
        alias="LOCAL_LLM_EMBEDDING_MODEL",
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    local_llm_embedding_timeout_seconds: float = Field(
        default=20.0,
        alias="LOCAL_LLM_EMBEDDING_TIMEOUT_SECONDS",
        ge=1.0,
        le=300.0,
    )
    embedding_provider: Literal["local", "openai", "local_http"] = Field(
        default="local",
        alias="EMBEDDING_PROVIDER",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBEDDING_MODEL",
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    openai_embedding_timeout_seconds: float = Field(
        default=10.0,
        alias="OPENAI_EMBEDDING_TIMEOUT_SECONDS",
        ge=1.0,
        le=60.0,
    )
    vector_backend: str = Field(default="json", alias="VECTOR_BACKEND")
    vector_embedding_dimensions: int = Field(default=64, alias="VECTOR_EMBEDDING_DIMENSIONS")
    memory_retrieval_top_k: int = Field(
        default=6,
        alias="MEMORY_RETRIEVAL_TOP_K",
        ge=1,
        le=50,
    )
    memory_retrieval_candidate_multiplier: int = Field(
        default=3,
        alias="MEMORY_RETRIEVAL_CANDIDATE_MULTIPLIER",
        ge=1,
        le=10,
    )
    memory_retrieval_profile_top_k: int = Field(
        default=2,
        alias="MEMORY_RETRIEVAL_PROFILE_TOP_K",
        ge=0,
        le=20,
    )
    memory_retrieval_episodic_top_k: int = Field(
        default=2,
        alias="MEMORY_RETRIEVAL_EPISODIC_TOP_K",
        ge=0,
        le=20,
    )
    memory_retrieval_semantic_top_k: int = Field(
        default=6,
        alias="MEMORY_RETRIEVAL_SEMANTIC_TOP_K",
        ge=0,
        le=50,
    )
    memory_context_max_chars: int = Field(
        default=800,
        alias="MEMORY_CONTEXT_MAX_CHARS",
        ge=50,
        le=10000,
    )
    memory_context_max_tokens: int = Field(
        default=220,
        alias="MEMORY_CONTEXT_MAX_TOKENS",
        ge=20,
        le=4000,
    )
    memory_weight_relevance: float = Field(
        default=0.65,
        alias="MEMORY_WEIGHT_RELEVANCE",
        ge=0.0,
        le=10.0,
    )
    memory_weight_importance: float = Field(
        default=0.25,
        alias="MEMORY_WEIGHT_IMPORTANCE",
        ge=0.0,
        le=10.0,
    )
    memory_weight_recency: float = Field(
        default=0.10,
        alias="MEMORY_WEIGHT_RECENCY",
        ge=0.0,
        le=10.0,
    )
    memory_policy_mode: Literal["rules", "llm"] = Field(
        default="rules",
        alias="MEMORY_POLICY_MODE",
    )
    memory_policy_min_confidence: float = Field(
        default=0.7,
        alias="MEMORY_POLICY_MIN_CONFIDENCE",
        ge=0.0,
        le=1.0,
    )
    jwt_secret_key: str = Field(
        default="change-me-in-production-at-least-32-chars",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("local_llm_base_url")
    @classmethod
    def validate_local_llm_base_url(cls, value: str) -> str:
        """Validate local LLM base URL format at settings load time."""

        base_url = value.strip()
        parsed = urlparse(base_url)
        if not base_url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("LOCAL_LLM_BASE_URL must be an absolute http(s) URL.")
        return base_url

    @field_validator(
        "openai_chat_model",
        "local_llm_chat_model",
        "local_llm_embedding_model",
        "openai_embedding_model",
        mode="before",
    )
    @classmethod
    def validate_model_names_not_blank(cls, value: str) -> str:
        """Normalize and reject blank model names."""

        if not isinstance(value, str):
            raise TypeError("Model name must be a string.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Model name must be non-empty.")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
