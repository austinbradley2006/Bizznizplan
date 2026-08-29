from __future__ import annotations

from robinhood_bot.client import RobinhoodService
from robinhood_bot.strategies.base import Signal, Strategy, StrategyDecision
from robinhood_bot.strategies.breakout import BreakoutStrategy
from robinhood_bot.strategies.indicators import bollinger_bands, macd, rsi, sma
from robinhood_bot.strategies.rsi import RSIStrategy
from robinhood_bot.strategies.sma_crossover import SMACrossoverStrategy


class CompositeStrategy(Strategy):
    """Vote across multiple strategies and technical factors for robust signals."""

    name = "composite"

    def __init__(
        self,
        min_bars: int = 35,
        buy_threshold: float = 0.55,
        sell_threshold: float = -0.55,
        rsi_period: int = 14,
        fast_period: int = 10,
        slow_period: int = 30,
        breakout_lookback: int = 20,
    ) -> None:
        self.min_bars = min_bars
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.rsi_strategy = RSIStrategy(period=rsi_period, min_bars=min_bars)
        self.sma_strategy = SMACrossoverStrategy(
            fast_period=fast_period,
            slow_period=slow_period,
            min_bars=min_bars,
        )
        self.breakout_strategy = BreakoutStrategy(
            lookback_period=breakout_lookback,
            min_bars=min_bars,
        )

    def _score_decision(self, decision: StrategyDecision) -> float:
        if decision.signal == Signal.BUY:
            return decision.confidence
        if decision.signal == Signal.SELL:
            return -decision.confidence
        return 0.0

    def evaluate(self, symbol: str, service: RobinhoodService) -> StrategyDecision:
        closes = service.get_closes(symbol)
        if len(closes) < self.min_bars:
            return StrategyDecision(
                signal=Signal.HOLD,
                reason=f"Not enough history ({len(closes)}/{self.min_bars} bars)",
                confidence=0.0,
            )

        votes: list[tuple[str, float]] = []
        for label, strategy in (
            ("RSI", self.rsi_strategy),
            ("SMA", self.sma_strategy),
            ("Breakout", self.breakout_strategy),
        ):
            decision = strategy.evaluate(symbol, service)
            votes.append((label, self._score_decision(decision)))

        current_rsi = rsi(closes, 14)
        if current_rsi is not None:
            if current_rsi <= 30:
                votes.append(("RSI-level", 0.8))
            elif current_rsi >= 70:
                votes.append(("RSI-level", -0.8))

        macd_line, signal_line, histogram = macd(closes)
        if macd_line is not None and signal_line is not None:
            if macd_line > signal_line and (histogram or 0) > 0:
                votes.append(("MACD", 0.6))
            elif macd_line < signal_line and (histogram or 0) < 0:
                votes.append(("MACD", -0.6))

        lower, middle, upper = bollinger_bands(closes)
        price = closes[-1]
        if lower is not None and upper is not None and middle is not None:
            if price <= lower:
                votes.append(("Bollinger", 0.5))
            elif price >= upper:
                votes.append(("Bollinger", -0.5))

        fast = sma(closes, 10)
        slow = sma(closes, 30)
        if fast is not None and slow is not None:
            if fast > slow:
                votes.append(("Trend", 0.4))
            else:
                votes.append(("Trend", -0.4))

        total_score = sum(score for _, score in votes) / max(len(votes), 1)
        contributors = ", ".join(f"{label}={score:+.2f}" for label, score in votes)

        if total_score >= self.buy_threshold:
            return StrategyDecision(
                signal=Signal.BUY,
                reason=f"Composite bullish ({total_score:+.2f}): {contributors}",
                confidence=min(total_score, 1.0),
            )

        if total_score <= self.sell_threshold:
            return StrategyDecision(
                signal=Signal.SELL,
                reason=f"Composite bearish ({total_score:+.2f}): {contributors}",
                confidence=min(abs(total_score), 1.0),
            )

        return StrategyDecision(
            signal=Signal.HOLD,
            reason=f"Composite neutral ({total_score:+.2f}): {contributors}",
            confidence=abs(total_score),
        )
