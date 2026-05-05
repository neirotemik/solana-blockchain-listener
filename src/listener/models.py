from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    TOKEN_CREATED = "token_created"
    TRADE_OBSERVED = "trade_observed"
    LIQUIDITY_EVENT = "liquidity_event"
    UNKNOWN = "unknown_pumpfun_event"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


class LiquidityKind(str, Enum):
    BONDING_CURVE_UPDATE = "bonding_curve_update"
    MIGRATION = "migration"
    UNKNOWN = "unknown"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    signature: str
    slot: int | None = None
    block_time: datetime | None = None
    received_at: datetime = Field(default_factory=_utcnow)
    program_id: str
    raw_logs: tuple[str, ...] = Field(default_factory=tuple)


class TokenCreated(_BaseEvent):
    event_type: Literal[EventType.TOKEN_CREATED] = EventType.TOKEN_CREATED
    mint: str | None = None
    creator: str | None = None
    name: str | None = None
    symbol: str | None = None
    uri: str | None = None
    bonding_curve: str | None = None


class TradeObserved(_BaseEvent):
    event_type: Literal[EventType.TRADE_OBSERVED] = EventType.TRADE_OBSERVED
    mint: str | None = None
    trader: str | None = None
    side: TradeSide = TradeSide.UNKNOWN
    sol_amount: float | None = None
    token_amount: float | None = None
    bonding_curve: str | None = None


class LiquidityEvent(_BaseEvent):
    event_type: Literal[EventType.LIQUIDITY_EVENT] = EventType.LIQUIDITY_EVENT
    kind: LiquidityKind = LiquidityKind.UNKNOWN
    mint: str | None = None
    bonding_curve: str | None = None
    sol_reserves: float | None = None
    token_reserves: float | None = None


class UnknownPumpFunEvent(_BaseEvent):
    event_type: Literal[EventType.UNKNOWN] = EventType.UNKNOWN
    reason: str | None = None


PumpFunEvent = Annotated[
    Union[TokenCreated, TradeObserved, LiquidityEvent, UnknownPumpFunEvent],
    Field(discriminator="event_type"),
]


class RawLogNotification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signature: str
    slot: int | None = None
    err: object | None = None
    logs: tuple[str, ...] = Field(default_factory=tuple)