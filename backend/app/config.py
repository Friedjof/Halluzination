from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    allowed_origins: list[str] = ["http://localhost:5173"]
    admin_token: str = "dev-token"
    database_url: str = "postgresql+asyncpg://halluzination:halluzination@localhost:5432/halluzination"
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://localhost:5173"
    upload_dir: str = "uploads"

    # Look for .env in parent dir first (local dev: running from backend/),
    # then current dir (Docker: env vars injected directly, fallback .env in /app)
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


settings = Settings()
