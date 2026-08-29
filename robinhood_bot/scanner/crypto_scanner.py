from __future__ import annotations

import logging

from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import CryptoScannerConfig
from robinhood_bot.scanner.models import ScanResult, TradeOpportunity
from robinhood_bot.strategies.base import Signal, Strategy
from robinhood_bot.strategies.indicators import rsi, sma

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class CryptoScanner:
    """Scan Robinhood crypto pairs for momentum and strategy signals."""

    def __init__(self, service: RobinhoodService, config: CryptoScannerConfig) -> None:
        self.service = service
        self.config = config

    def _resolve_pairs(self) -> list[str]:
        if self.config.pairs:
            return [pair.upper() for pair in self.config.pairs]

        pairs = self.service.get_crypto_tradable_pairs()
        return pairs[: self.config.max_pairs]

    def _evaluate_pair(self, pair: str, strategy: Strategy | None) -> TradeOpportunity | None:
        closes = self.service.get_crypto_closes(
            pair,
            interval=self.config.interval,
            span=self.config.span,
        )
        if len(closes) < self.config.min_bars:
            return None

        quote = self.service.get_crypto_quote(pair)
        price = (quote.bid + quote.ask) / 2 if quote else closes[-1]
        change_pct = 0.0
        if len(closes) >= 2 and closes[-2] > 0:
            change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100

        signal = Signal.HOLD.value
        reason = "Crypto scan"
        strategy_bonus = 0.0

        if strategy is not None:
            decision = strategy.evaluate(pair, self.service)
            signal = decision.signal.value
            reason = decision.reason
            if decision.signal == Signal.BUY:
                strategy_bonus = 0.25
            elif decision.signal == Signal.SELL:
                strategy_bonus = -0.2
        else:
            current_rsi = rsi(closes, self.config.rsi_period)
            fast = sma(closes, self.config.fast_period)
            slow = sma(closes, self.config.slow_period)
            if current_rsi is not None and current_rsi <= self.config.oversold:
                signal = Signal.BUY.value
                reason = f"RSI oversold at {current_rsi:.1f}"
                strategy_bonus = 0.2
            elif current_rsi is not None and current_rsi >= self.config.overbought:
                signal = Signal.SELL.value
                reason = f"RSI overbought at {current_rsi:.1f}"
                strategy_bonus = 0.2
            elif fast is not None and slow is not None and fast > slow:
                signal = Signal.BUY.value
                reason = f"Bullish SMA ({fast:.4f} > {slow:.4f})"
                strategy_bonus = 0.1

        momentum = _clamp((change_pct + 5.0) / 10.0)
        score = _clamp(momentum * 0.4 + 0.35 + strategy_bonus)

        if score < self.config.min_score and signal == Signal.HOLD.value:
            return None

        return TradeOpportunity(
            symbol=pair,
            asset_type="crypto",
            score=score,
            signal=signal,
            reason=reason,
            price=price,
            change_pct=change_pct,
            sources=["crypto:tradable"],
            metrics={
                "momentum": momentum,
                "strategy_bonus": strategy_bonus,
            },
        )

    def scan(self, strategy: Strategy | None = None) -> ScanResult:
        if not self.service.crypto_available():
            logger.warning(
                "Crypto API not configured. Run `pyhood setup crypto` to enable crypto scanning."
            )
            return ScanResult(
                market="crypto",
                scanned_symbols=0,
                evaluated_symbols=0,
                opportunities=[],
                buy_candidates=[],
                sell_candidates=[],
            )

        pairs = self._resolve_pairs()
        opportunities: list[TradeOpportunity] = []

        for pair in pairs:
            try:
                opportunity = self._evaluate_pair(pair, strategy)
                if opportunity is not None:
                    opportunities.append(opportunity)
            except Exception:
                logger.exception("Failed crypto scan for %s", pair)

        opportunities.sort(key=lambda item: item.score, reverse=True)
        top = opportunities[: self.config.top_opportunities]
        return ScanResult(
            market="crypto",
            scanned_symbols=len(pairs),
            evaluated_symbols=len(opportunities),
            opportunities=top,
            buy_candidates=[item for item in top if item.signal == Signal.BUY.value],
            sell_candidates=[item for item in top if item.signal == Signal.SELL.value],
        )
