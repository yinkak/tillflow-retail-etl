"""Pipeline settings, loaded once from environment variables / .env."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

VALID_STORAGE_MODES = {"azurite", "azure"}


@dataclass(frozen=True)
class Settings:
    storage_mode: str
    azure_storage_account: str
    container_raw: str
    container_landing: str
    azurite_connection_string: str
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    chunk_size: int
    log_level: str

    @property
    def postgres_dsn(self) -> str:
        """Connection string psycopg uses to reach Postgres."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def get_settings() -> Settings:
    """Read settings from the environment (and .env if present) and validate them."""
    load_dotenv()

    storage_mode = os.getenv("STORAGE_MODE", "azurite")
    if storage_mode not in VALID_STORAGE_MODES:
        raise ValueError(
            f"STORAGE_MODE must be one of {sorted(VALID_STORAGE_MODES)}, got {storage_mode!r}"
        )

    return Settings(
        storage_mode=storage_mode,
        azure_storage_account=os.getenv("AZURE_STORAGE_ACCOUNT", ""),
        container_raw=os.getenv("AZURE_CONTAINER_RAW", "raw"),
        container_landing=os.getenv("AZURE_CONTAINER_LANDING", "landing"),
        azurite_connection_string=os.getenv(
            "AZURITE_CONNECTION_STRING", "UseDevelopmentStorage=true"
        ),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5433")),
        postgres_user=os.getenv("POSTGRES_USER", "tillflow"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "tillflow"),
        postgres_db=os.getenv("POSTGRES_DB", "retail"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "50000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
