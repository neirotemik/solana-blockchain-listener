from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

Commitment = Literal["processed", "confirmed", "finalized"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LISTENER_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rpc_ws_url: str = Field(default="wss://api.mainnet-beta.solana.com")
    rpc_http_url: HttpUrl = Field(default="https://api.mainnet-beta.solana.com")  # type: ignore[assignment]

    pumpfun_program_id: str = Field(
        default="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        description="pump.fun program ID. Configurable to allow protocol updates.",
    )

    commitment: Commitment = Field(default="confirmed")

    queue_max_size: int = Field(default=10_000, ge=1)
    dedupe_capacity: int = Field(default=50_000, ge=1)

    reconnect_initial_delay: float = Field(default=1.0, ge=0.0)
    reconnect_max_delay: float = Field(default=30.0, ge=0.1)
    reconnect_factor: float = Field(default=2.0, ge=1.0)

    ws_ping_interval: float = Field(default=20.0, ge=1.0)
    ws_ping_timeout: float = Field(default=20.0, ge=1.0)
    ws_open_timeout: float = Field(default=15.0, ge=1.0)
    ws_max_message_size: int = Field(default=8 * 1024 * 1024, ge=1024)

    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)