from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    ENV: str = "development"

    JWT_ACCESS_SECRET: str | None = None
    JWT_REFRESH_SECRET: str | None = None
    JWT_SECRET: str | None = None
    JWT_ACCESS_EXPIRES_IN: str = "15m"
    JWT_REFRESH_EXPIRES_IN: str = "7d"

    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_API_KEY: str | None = None
    LLM_API_KEY: str = "placeholder-local-key"
    LLM_PROVIDER: str = "placeholder"
    LLM_TIMEOUT_SECONDS: float = 30.0
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    AWS_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_ENDPOINT: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET_NAME: str = "vault-bucket"
    AWS_REGION: str = "us-east-1"

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def use_async_database_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

def get_settings() -> Settings:
    return Settings()

# Singleton instance ready to import anywhere
settings = get_settings()