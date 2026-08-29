from __future__ import annotations

from robinhood_bot.client import RobinhoodService
from robinhood_bot.strategies.base import Signal, Strategy, StrategyDecision


class BreakoutStrategy(Strategy):
    """Buy on breakout above recent range high; sell on breakdown below range low."""

    name = "breakout"

    def __init__(
        self,
        lookback_period: int = 20,
        min_bars: int = 25,
        span: str = "month",
        interval: str = "day",
    ) -> None:
        self.lookback_period = lookback_period
        self.min_bars = min_bars
        self.span = span
        self.interval = interval

    def evaluate(self, symbol: str, service: RobinhoodService) -> StrategyDecision:
        closes = service.get_closes(symbol, span=self.span, interval=self.interval)
        if len(closes) < self.min_bars:
            return StrategyDecision(
                signal=Signal.HOLD,
                reason=f"Not enough history ({len(closes)}/{self.min_bars} bars)",
            )

        window = closes[-(self.lookback_period + 1):-1]
        if len(window) < self.lookback_period:
            return StrategyDecision(signal=Signal.HOLD, reason="Insufficient breakout window")

        range_high = max(window)
        range_low = min(window)
        price = closes[-1]

        if price > range_high:
            return StrategyDecision(
                signal=Signal.BUY,
                reason=(
                    f"Price ${price:.2f} broke above {self.lookback_period}-bar high "
                    f"${range_high:.2f}"
                ),
                confidence=0.7,
            )

        if price < range_low:
            return StrategyDecision(
                signal=Signal.SELL,
                reason=(
                    f"Price ${price:.2f} broke below {self.lookback_period}-bar low "
                    f"${range_low:.2f}"
                ),
                confidence=0.7,
            )

        return StrategyDecision(
            signal=Signal.HOLD,
            reason=(
                f"Inside range ${range_low:.2f}-${range_high:.2f} "
                f"(price ${price:.2f})"
            ),
        )
