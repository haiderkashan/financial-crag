from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings validated using Pydantic Settings."""

    PROJECT_NAME: str = "Financial SEC Due-Diligence CRAG API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security & JWT
    JWT_SECRET: str = "default-dev-secret-change-in-production-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    # Supabase (Database & pgvector)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    @property
    def effective_supabase_key(self) -> str:
        """Returns the service key or service role key provided in environment."""
        return self.SUPABASE_SERVICE_KEY or self.SUPABASE_SERVICE_ROLE_KEY

    # SMTP Configuration
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "sec-agent@financialcrag.local"
    SMTP_USE_TLS: bool = True
    SMTP_DEV_MODE: bool = True

    # SEC EDGAR Configuration
    SEC_EDGAR_USER_AGENT: str = "FinancialCRAG admin@example.com"
    SEC_EDGAR_BASE_URL: str = "https://data.sec.gov"
    SEC_EDGAR_RATE_LIMIT_RPS: int = 8
    DATA_DIR: str = "data/filings"

    # LlamaParse Configuration
    LLAMA_CLOUD_API_KEY: str = ""
    LLAMA_PARSE_RESULT_TYPE: str = "markdown"
    LLAMA_PARSE_NUM_WORKERS: int = 4

    # Embedding Model Configuration (BAAI/bge-small-en-v1.5)
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32

    # CORS & Frontend Origins
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            import json
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except Exception:
                    return [v]
            return v
        return ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
