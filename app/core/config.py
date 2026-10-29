from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    environment: str = "development"
    log_level: str = "INFO"
    mongodb_uri: SecretStr = SecretStr("mongodb://localhost:27017")
    db_name: str = "cropmind"
    jwt_secret: SecretStr = SecretStr("development-only-change-this-secret-32-chars")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: int = Field(default=8, ge=1, le=30)
    frontend_origin: str = "http://localhost:3000"
    cron_secret: SecretStr | None = None
    simulator_enabled: bool = False
    admin_seed_email: str | None = None
    admin_seed_password: SecretStr | None = None
    seed_token: SecretStr | None = None

    @field_validator("frontend_origin", mode="before")
    @classmethod
    def normalize_frontend_origin(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self):
        if self.environment == "production" and len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters in production")
        if self.jwt_algorithm != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256 for this implementation")
        if self.environment == "production" and self.frontend_origin.startswith("http://"):
            raise ValueError("FRONTEND_ORIGIN must use HTTPS in production")
        if self.seed_token is not None and len(self.seed_token.get_secret_value()) < 32:
            raise ValueError("SEED_TOKEN must contain at least 32 characters")
        if self.cron_secret is not None and len(self.cron_secret.get_secret_value()) < 32:
            raise ValueError("CRON_SECRET must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
