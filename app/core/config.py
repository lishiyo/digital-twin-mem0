from typing import Any, List, Dict, Optional, Union
import os

from pydantic import PostgresDsn, field_validator, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "digital-twin-dao"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"  # Frontend URL

    # Database
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5433  # Changed to int with default 5433
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: PostgresDsn | None = None
    SYNC_SQLALCHEMY_DATABASE_URI: PostgresDsn | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: str | None, info: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_HOST"),
            port=info.data.get("POSTGRES_PORT"),  # This is now an int
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    @field_validator("SYNC_SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_sync_db_connection(cls, v: str | None, info: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+psycopg2",  # Use the synchronous driver
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_HOST"),
            port=info.data.get("POSTGRES_PORT"),
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    # Redis
    REDIS_HOST: str
    REDIS_PORT: str = "6379"
    REDIS_PASSWORD: str = ""
    REDIS_URL: str | None = None

    @field_validator("REDIS_URL", mode="before")
    def assemble_redis_connection(cls, v: str | None, info: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        password = f":{info.data.get('REDIS_PASSWORD')}@" if info.data.get("REDIS_PASSWORD") else ""
        return f"redis://{password}{info.data.get('REDIS_HOST')}:{info.data.get('REDIS_PORT')}/0"

    # Neo4j (for Graphiti)
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    # Mem0
    MEM0_API_KEY: str

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.7

    # Entity, relationship, trait Extraction
    GEMINI_API_KEY: str | None = None

    ENABLE_PROFILE_UPDATES: bool = False
    ENABLE_GRAPHITI_INGESTION: bool = True

    # Auth
    # AUTH0_DOMAIN: str
    # AUTH0_API_AUDIENCE: str
    # AUTH0_ALGORITHMS: list[str] = ["RS256"]

    # Storage
    STORAGE_BUCKET: str
    STORAGE_ENDPOINT: str = "https://s3.wasabisys.com"
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_KEY: str
    
    # File ingestion
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

    # Additional settings that might be in .env
    TELEGRAM_APP_ID: str | None = None
    TELEGRAM_APP_HASH: str | None = None
    WEAVIATE_URL: str | None = None
    WEAVIATE_API_KEY: str | None = None
    STORAGE_REGION: str | None = None
    EMBEDDING_MODEL: str | None = None
    DEBUG: bool = False
    SECRET_KEY: str | None = None
    TOKEN_EXPIRE_MINUTES: int | None = None
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    GRAPHITI_HOST: str | None = None
    GRAPHITI_PORT: str | None = None

    # Test Database - SQLite in-memory for tests
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",  # Allow extra fields from environment variables
    )


settings = Settings()
