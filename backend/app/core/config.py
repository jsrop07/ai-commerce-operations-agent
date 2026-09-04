"""Environment configuration with fail-closed write defaults."""

from enum import StrEnum

from pydantic import Field, model_validator
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
    database_url: str = "postgresql+psycopg://commerce:commerce@localhost:5432/commerce_ops"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def enforce_production_read_only(self) -> "Settings":
        if self.environment == Environment.PRODUCTION_READ:
            if self.write_mode != WriteMode.DISABLED or not self.global_write_kill:
                raise ValueError("PRODUCTION_READ requires disabled writes and global kill enabled")
        return self


def get_settings() -> Settings:
    return Settings()
