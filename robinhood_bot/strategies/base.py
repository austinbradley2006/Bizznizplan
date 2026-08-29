from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from robinhood_bot.client import RobinhoodService


class Signal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategyDecision:
    signal: Signal
    reason: str


class Strategy:
    name = "base"

    def evaluate(self, symbol: str, service: RobinhoodService) -> StrategyDecision:
        raise NotImplementedError
