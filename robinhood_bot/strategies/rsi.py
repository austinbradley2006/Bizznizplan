from __future__ import annotations

from robinhood_bot.client import RobinhoodService
from robinhood_bot.strategies.base import Signal, Strategy, StrategyDecision
from robinhood_bot.strategies.indicators import rsi


class RSIStrategy(Strategy):
    """Buy oversold, sell overbought using RSI."""

    name = "rsi"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        min_bars: int = 20,
    ) -> None:
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.min_bars = min_bars

    def evaluate(self, symbol: str, service: RobinhoodService) -> StrategyDecision:
        closes = service.get_closes(symbol)
        if len(closes) < self.min_bars:
            return StrategyDecision(
                signal=Signal.HOLD,
                reason=f"Not enough history ({len(closes)}/{self.min_bars} bars)",
            )

        current_rsi = rsi(closes, self.period)
        if current_rsi is None:
            return StrategyDecision(signal=Signal.HOLD, reason="Insufficient RSI data")

        if current_rsi <= self.oversold:
            return StrategyDecision(
                signal=Signal.BUY,
                reason=f"RSI oversold at {current_rsi:.1f} (threshold {self.oversold})",
                confidence=min((self.oversold - current_rsi) / self.oversold + 0.5, 1.0),
            )

        if current_rsi >= self.overbought:
            return StrategyDecision(
                signal=Signal.SELL,
                reason=f"RSI overbought at {current_rsi:.1f} (threshold {self.overbought})",
                confidence=min((current_rsi - self.overbought) / (100 - self.overbought) + 0.5, 1.0),
            )

        return StrategyDecision(
            signal=Signal.HOLD,
            reason=f"RSI neutral at {current_rsi:.1f}",
        )
