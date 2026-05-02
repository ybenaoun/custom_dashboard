from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cohere_api_key: str
    cohere_model: str = "command-a-03-2025"
    cohere_temperature: float = 0.3
    cohere_max_tokens: int = 800
    cohere_max_tool_rounds: int = 3

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    frappe_url: str = "http://erpnext.localhost:8000"
    frappe_host_header: str | None = None
    frappe_tool_timeout: float = 30.0

    database_url: str | None = None
    rag_internal_api_key: str | None = None
    rag_embed_model: str = "embed-multilingual-v3.0"
    rag_rerank_model: str = "rerank-v3.5"
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 150
    rag_top_k: int = 24
    rag_rerank_top_n: int = 8
    rag_min_relevance: float = 0.15
    rag_db_pool_size: int = 5
    rag_chat_enabled: bool = True

    voice_enabled: bool = True
    voice_gateway_url: str = "http://127.0.0.1:8010"
    voice_gateway_timeout: float = 60.0
    stt_max_bytes: int = 25 * 1024 * 1024

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://erpnext.localhost:8000"]
    )


settings = Settings()
