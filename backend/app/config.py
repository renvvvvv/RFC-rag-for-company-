"""Application settings loaded from environment variables."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Enterprise Private RAG"
    DEBUG: bool = False

    # PostgreSQL
    POSTGRES_USER: str = "rag"
    POSTGRES_PASSWORD: str = "rag"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "rag"
    DATABASE_URL: str | None = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str | None = None

    # RabbitMQ / AMQP
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_URL: str | None = None

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_PREFIX: str = "rag"

    # MinIO (S3-compatible)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "rag-documents"
    MINIO_SECURE: bool = False

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Model service endpoints
    EMBEDDING_SERVICE_URL: str = "http://localhost:8001/embed"
    EMBEDDING_API_URL: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_API_KEY: str | None = None
    EMBEDDING_DIMENSION: int = 768

    RERANK_SERVICE_URL: str = "http://localhost:8002/rerank"
    RERANK_API_URL: str | None = None
    RERANK_MODEL: str = "bge-reranker-large"
    RERANK_API_KEY: str | None = None

    LLM_API_URL: str | None = None
    LLM_MODEL: str = "minimax-m3"
    LLM_API_KEY: str | None = None
    MINIMAX_API_KEY: str | None = None
    MINIMAX_BASE_URL: str = "https://api.minimax.chat"

    @property
    def async_database_url(self) -> str:
        """Return asyncpg-compatible database URL."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL or f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def rabbitmq_url(self) -> str:
        return (
            self.RABBITMQ_URL
            or f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"
        )


settings = Settings()
