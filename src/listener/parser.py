from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from listener.models import (
    EventType,
    LiquidityEvent,
    LiquidityKind,
    PumpFunEvent,
    RawLogNotification,
    TokenCreated,
    TradeObserved,
    TradeSide,
    UnknownPumpFunEvent,
)


class PumpFunParser(ABC):
    @abstractmethod
    def parse(self, notification: RawLogNotification, program_id: str) -> PumpFunEvent: ...


_CREATE_PATTERNS = (
    re.compile(r"\bInstruction:\s*Create(Token|Coin|Mint)?\b", re.IGNORECASE),
    re.compile(r"\bInitializeMint\b", re.IGNORECASE),
    re.compile(r"\bcreate\s+token\b", re.IGNORECASE),
)

_BUY_PATTERNS = (
    re.compile(r"\bInstruction:\s*Buy\b", re.IGNORECASE),
)

_SELL_PATTERNS = (
    re.compile(r"\bInstruction:\s*Sell\b", re.IGNORECASE),
)

_LIQUIDITY_PATTERNS = (
    re.compile(r"\bbonding\s*curve\b", re.IGNORECASE),
    re.compile(r"\bmigrat", re.IGNORECASE),
    re.compile(r"\bWithdraw\b", re.IGNORECASE),
)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


class HeuristicLogParser(PumpFunParser):
    def parse(self, notification: RawLogNotification, program_id: str) -> PumpFunEvent:
        logs = notification.logs
        joined = "\n".join(logs)

        base_kwargs = {
            "signature": notification.signature,
            "slot": notification.slot,
            "block_time": datetime.now(timezone.utc),
            "program_id": program_id,
            "raw_logs": logs,
        }

        if notification.err is not None:
            return UnknownPumpFunEvent(**base_kwargs, reason="transaction_error")

        if _matches_any(joined, _CREATE_PATTERNS):
            return TokenCreated(**base_kwargs)

        is_buy = _matches_any(joined, _BUY_PATTERNS)
        is_sell = _matches_any(joined, _SELL_PATTERNS)
        if is_buy or is_sell:
            side = TradeSide.BUY if is_buy and not is_sell else (
                TradeSide.SELL if is_sell and not is_buy else TradeSide.UNKNOWN
            )
            return TradeObserved(**base_kwargs, side=side)

        if _matches_any(joined, _LIQUIDITY_PATTERNS):
            joined_lower = joined.lower()
            if "migrat" in joined_lower:
                kind = LiquidityKind.MIGRATION
            elif "bonding" in joined_lower:
                kind = LiquidityKind.BONDING_CURVE_UPDATE
            else:
                kind = LiquidityKind.UNKNOWN
            return LiquidityEvent(**base_kwargs, kind=kind)

        return UnknownPumpFunEvent(**base_kwargs, reason="no_matching_heuristic")


def event_identity(event: PumpFunEvent) -> str:
    return f"{event.signature}:{event.event_type.value}"