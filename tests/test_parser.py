from listener.models import (
    EventType,
    LiquidityKind,
    TradeSide,
)
from listener.parser import HeuristicLogParser, event_identity
from listener.models import RawLogNotification

PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


def _notif(logs: tuple[str, ...], err: object | None = None) -> RawLogNotification:
    return RawLogNotification(
        signature="sig123",
        slot=1,
        err=err,
        logs=logs,
    )


def test_parses_token_creation() -> None:
    parser = HeuristicLogParser()
    logs = (
        "Program log: Instruction: Create",
        "Program log: InitializeMint",
    )
    event = parser.parse(_notif(logs), PROGRAM_ID)
    assert event.event_type == EventType.TOKEN_CREATED
    assert event.signature == "sig123"
    assert event.program_id == PROGRAM_ID


def test_parses_buy_trade() -> None:
    parser = HeuristicLogParser()
    logs = ("Program log: Instruction: Buy",)
    event = parser.parse(_notif(logs), PROGRAM_ID)
    assert event.event_type == EventType.TRADE_OBSERVED
    assert event.side == TradeSide.BUY


def test_parses_sell_trade() -> None:
    parser = HeuristicLogParser()
    logs = ("Program log: Instruction: Sell",)
    event = parser.parse(_notif(logs), PROGRAM_ID)
    assert event.event_type == EventType.TRADE_OBSERVED
    assert event.side == TradeSide.SELL


def test_parses_liquidity_event() -> None:
    parser = HeuristicLogParser()
    logs = ("Program log: bonding curve updated",)
    event = parser.parse(_notif(logs), PROGRAM_ID)
    assert event.event_type == EventType.LIQUIDITY_EVENT
    assert event.kind == LiquidityKind.BONDING_CURVE_UPDATE


def test_parses_migration() -> None:
    parser = HeuristicLogParser()
    logs = ("Program log: migrating to raydium",)
    event = parser.parse(_notif(logs), PROGRAM_ID)
    assert event.event_type == EventType.LIQUIDITY_EVENT
    assert event.kind == LiquidityKind.MIGRATION


def test_unknown_event_when_no_heuristic_matches() -> None:
    parser = HeuristicLogParser()
    logs = ("Program log: something unrelated",)
    event = parser.parse(_notif(logs), PROGRAM_ID)
    assert event.event_type == EventType.UNKNOWN


def test_failed_tx_is_unknown_with_reason() -> None:
    parser = HeuristicLogParser()
    logs = ("Program log: Instruction: Buy",)
    event = parser.parse(_notif(logs, err={"InstructionError": []}), PROGRAM_ID)
    assert event.event_type == EventType.UNKNOWN
    assert getattr(event, "reason", None) == "transaction_error"


def test_event_identity_is_stable() -> None:
    parser = HeuristicLogParser()
    e1 = parser.parse(_notif(("Program log: Instruction: Buy",)), PROGRAM_ID)
    e2 = parser.parse(_notif(("Program log: Instruction: Buy",)), PROGRAM_ID)
    assert event_identity(e1) == event_identity(e2)