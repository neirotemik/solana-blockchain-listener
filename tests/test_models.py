import json
from datetime import datetime, timezone

from listener.models import (
    EventType,
    LiquidityEvent,
    LiquidityKind,
    TokenCreated,
    TradeObserved,
    TradeSide,
    UnknownPumpFunEvent,
)


def _common() -> dict:
    return {
        "signature": "abc",
        "slot": 100,
        "block_time": datetime.now(timezone.utc),
        "program_id": "PROG",
        "raw_logs": ("log1", "log2"),
    }


def test_token_created_serializes() -> None:
    event = TokenCreated(**_common(), mint="mint1", creator="creator1")
    payload = json.loads(event.model_dump_json())
    assert payload["event_type"] == EventType.TOKEN_CREATED.value
    assert payload["mint"] == "mint1"


def test_trade_observed_default_side_unknown() -> None:
    event = TradeObserved(**_common())
    assert event.side == TradeSide.UNKNOWN


def test_liquidity_event_kind() -> None:
    event = LiquidityEvent(**_common(), kind=LiquidityKind.MIGRATION)
    assert event.kind == LiquidityKind.MIGRATION


def test_unknown_event_reason() -> None:
    event = UnknownPumpFunEvent(**_common(), reason="no_match")
    assert event.reason == "no_match"


def test_events_are_immutable() -> None:
    event = TokenCreated(**_common())
    try:
        event.signature = "changed"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("event should be frozen")