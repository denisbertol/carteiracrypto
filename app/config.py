"""Módulo de configuração da aplicação carteira-crypto."""

from decimal import Decimal
from datetime import datetime
import os
from functools import lru_cache
from typing import Optional
from uuid import UUID

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field, SecretStr, model_validator

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        app_env: str = Field(default="development", alias="APP_ENV")
        host: str = Field(default="0.0.0.0", alias="HOST")
        port: int = Field(default=8000, alias="PORT")

        database_url: str = Field(
            default="postgresql://carteira_app:senha@localhost:5432/postgres",
            alias="DATABASE_URL",
        )
        migration_database_url: Optional[str] = Field(
            default=None, alias="MIGRATION_DATABASE_URL"
        )

        supabase_url: str = Field(default="https://exemplo.supabase.co", alias="SUPABASE_URL")
        supabase_publishable_key: str = Field(
            default="anon-key", alias="SUPABASE_PUBLISHABLE_KEY"
        )
        owner_user_id: UUID = Field(
            default=UUID("00000000-0000-0000-0000-000000000000"),
            alias="OWNER_USER_ID",
        )

        quote_mode: str = Field(default="unavailable", alias="QUOTE_MODE")
        demo_quote_usd: Decimal = Field(default=Decimal("180"), alias="DEMO_QUOTE_USD")
        coingecko_demo_api_key: SecretStr = Field(default=SecretStr(""), alias="COINGECKO_DEMO_API_KEY")
        coingecko_call_limit: int = Field(default=10000, ge=1, alias="COINGECKO_CALL_LIMIT")
        coingecko_window_start: Optional[datetime] = Field(default=None, alias="COINGECKO_WINDOW_START")
        coingecko_window_end: Optional[datetime] = Field(default=None, alias="COINGECKO_WINDOW_END")

        @model_validator(mode="after")
        def validate_monitoring(self):
            validate_quote_config(self)
            return self

        pool_min_size: int = Field(default=1, alias="POOL_MIN_SIZE")
        pool_max_size: int = Field(default=10, alias="POOL_MAX_SIZE")
        pool_timeout_seconds: float = Field(default=10.0, alias="POOL_TIMEOUT_SECONDS")
        lock_timeout_seconds: float = Field(default=5.0, alias="LOCK_TIMEOUT_SECONDS")
        statement_timeout_seconds: float = Field(
            default=15.0, alias="STATEMENT_TIMEOUT_SECONDS"
        )


except ImportError:
    # Fallback leve caso pydantic-settings não esteja instalado no ambiente local
    class Settings:  # type: ignore
        def __init__(self) -> None:
            self.app_env = os.getenv("APP_ENV", "development")
            self.host = os.getenv("HOST", "0.0.0.0")
            self.port = int(os.getenv("PORT", "8000"))
            self.database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://carteira_app:senha@localhost:5432/postgres",
            )
            self.migration_database_url = os.getenv("MIGRATION_DATABASE_URL")
            self.supabase_url = os.getenv(
                "SUPABASE_URL", "https://exemplo.supabase.co"
            )
            self.supabase_publishable_key = os.getenv(
                "SUPABASE_PUBLISHABLE_KEY", "anon-key"
            )
            raw_owner = os.getenv(
                "OWNER_USER_ID", "00000000-0000-0000-0000-000000000000"
            )
            self.owner_user_id = UUID(raw_owner)
            self.quote_mode = os.getenv("QUOTE_MODE", "unavailable")
            self.demo_quote_usd = Decimal(os.getenv("DEMO_QUOTE_USD", "180"))
            self.coingecko_demo_api_key = HiddenSecret(os.getenv("COINGECKO_DEMO_API_KEY", ""))
            self.coingecko_call_limit = int(os.getenv("COINGECKO_CALL_LIMIT", "10000"))
            self.coingecko_window_start = parse_window(os.getenv("COINGECKO_WINDOW_START"))
            self.coingecko_window_end = parse_window(os.getenv("COINGECKO_WINDOW_END"))
            validate_quote_config(self)
            self.pool_min_size = int(os.getenv("POOL_MIN_SIZE", "1"))
            self.pool_max_size = int(os.getenv("POOL_MAX_SIZE", "3"))
            self.pool_timeout_seconds = float(
                os.getenv("POOL_TIMEOUT_SECONDS", "2.0")
            )
            self.lock_timeout_seconds = float(
                os.getenv("LOCK_TIMEOUT_SECONDS", "2.0")
            )
            self.statement_timeout_seconds = float(
                os.getenv("STATEMENT_TIMEOUT_SECONDS", "5.0")
            )


class HiddenSecret:
    """Fallback that does not include credentials in str/repr."""

    def __init__(self, value: str):
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "HiddenSecret('**********')"

    __str__ = __repr__


def parse_window(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def validate_quote_config(settings) -> None:
    if settings.quote_mode not in {"unavailable", "coingecko", "cryptoprices", "fixture", "mock_stale"}:
        raise ValueError("QUOTE_MODE inválido")
    if settings.quote_mode in {"fixture", "mock_stale"} and settings.app_env not in {"development", "test"}:
        raise ValueError("Cotações demonstrativas são proibidas fora de development/test")
    if settings.coingecko_call_limit < 1:
        raise ValueError("COINGECKO_CALL_LIMIT deve ser positivo")
    start, end = settings.coingecko_window_start, settings.coingecko_window_end
    if (start is None) != (end is None):
        raise ValueError("Configure ambos os limites da janela CoinGecko")
    if start is not None and (start.utcoffset() is None or end.utcoffset() is None or start >= end):
        raise ValueError("Janela CoinGecko deve ter timezone e início anterior ao fim")


def provider_configured(settings, now: datetime) -> bool:
    """Missing/expired operator configuration means unavailable, never free calls."""
    if settings.quote_mode == "cryptoprices":
        return True
    start, end = settings.coingecko_window_start, settings.coingecko_window_end
    return bool(settings.quote_mode == "coingecko"
                and settings.coingecko_demo_api_key.get_secret_value()
                and start is not None and end is not None and start <= now < end)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância única cacheada das configurações."""
    return Settings()
