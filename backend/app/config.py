from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EduGuard API"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./eduguard.db"
    frontend_origin: str = "http://localhost:5173"

    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "deepseek-v4-flash"
    llm_timeout_seconds: float = 20.0
    behavior_classifier_mode: str = "auto"
    behavior_classifier_path: str | None = (
        "data/models/studychat_behavior_tfidf_logreg.joblib"
    )
    behavior_classifier_min_confidence: float = 0.5
    jwt_secret: str = "replace-this-development-secret"
    jwt_expire_minutes: int = 720

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
