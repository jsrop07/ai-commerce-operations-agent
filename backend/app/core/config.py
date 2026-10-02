"""Environment configuration with fail-closed write defaults."""
import uuid
from enum import StrEnum

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "LOCAL"
    TEST = "TEST"
    DEMO = "DEMO"
    PRODUCTION_READ = "PRODUCTION_READ"
    PILOT_SHADOW = "PILOT_SHADOW"
    PILOT_APPROVED = "PILOT_APPROVED"


class WriteMode(StrEnum):
    DISABLED = "disabled"
    DEMO_ONLY = "demo_only"
    PILOT_APPROVED = "pilot_approved"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Environment = Environment.LOCAL
    tenant_id: str = Field(default="demo_store", min_length=1)
    write_mode: WriteMode = WriteMode.DISABLED
    global_write_kill: bool = True
    database_url: str = ("postgresql+psycopg://commerce:commerce@localhost:5432/commerce_test")
    postgres_v2_url: str | None = None
    v2_tenant_id: uuid.UUID | None = None
    log_level: str = "INFO"
    retrieval_method: str | None = None  # None follows the handoff selection.
    retrieval_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    openai_api_key: SecretStr | None = None

    cafe24_mall_id: str | None = None
    cafe24_access_token: str | None = None
    cafe24_api_version: str | None = None

    cafe24_client_id: str | None = None
    cafe24_client_secret: str | None = None
    cafe24_redirect_uri: str | None = None
    cafe24_protected_data_dir: str | None = None
    
    @model_validator(mode="after")
    def enforce_production_read_only(self) -> "Settings":
        if self.environment == Environment.PRODUCTION_READ:
            if self.write_mode != WriteMode.DISABLED or not self.global_write_kill:
                raise ValueError("PRODUCTION_READ requires disabled writes and global kill enabled")
        return self


def get_settings() -> Settings:
    return Settings()
