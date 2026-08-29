from __future__ import annotations

from robinhood_bot.client import RobinhoodService
from robinhood_bot.strategies.base import Signal, Strategy, StrategyDecision
from robinhood_bot.strategies.indicators import sma as _sma


class SMACrossoverStrategy(Strategy):
    """Buy when fast SMA crosses above slow SMA; sell on cross below."""

    name = "sma_crossover"

    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 30,
        min_bars: int = 35,
    ) -> None:
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.min_bars = min_bars

    def evaluate(self, symbol: str, service: RobinhoodService) -> StrategyDecision:
        closes = service.get_closes(symbol)
        if len(closes) < self.min_bars:
            return StrategyDecision(
                signal=Signal.HOLD,
                reason=f"Not enough history ({len(closes)}/{self.min_bars} bars)",
            )

        prior = closes[:-1]
        current = closes

        fast_prev = _sma(prior, self.fast_period)
        slow_prev = _sma(prior, self.slow_period)
        fast_now = _sma(current, self.fast_period)
        slow_now = _sma(current, self.slow_period)

        if None in (fast_prev, slow_prev, fast_now, slow_now):
            return StrategyDecision(signal=Signal.HOLD, reason="Insufficient SMA data")

        if fast_prev <= slow_prev and fast_now > slow_now:
            return StrategyDecision(
                signal=Signal.BUY,
                reason=f"Fast SMA ({fast_now:.2f}) crossed above slow SMA ({slow_now:.2f})",
            )

        if fast_prev >= slow_prev and fast_now < slow_now:
            return StrategyDecision(
                signal=Signal.SELL,
                reason=f"Fast SMA ({fast_now:.2f}) crossed below slow SMA ({slow_now:.2f})",
            )

        return StrategyDecision(
            signal=Signal.HOLD,
            reason=f"No crossover (fast={fast_now:.2f}, slow={slow_now:.2f})",
        )
