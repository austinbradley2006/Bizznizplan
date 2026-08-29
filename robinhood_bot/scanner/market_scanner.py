from __future__ import annotations

import logging
from dataclasses import dataclass, field

from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import ScannerConfig
from robinhood_bot.strategies.base import Signal, Strategy

logger = logging.getLogger(__name__)

DEFAULT_DISCOVERY_TAGS = (
    "100-most-popular",
    "10-most-popular",
    "top-movers",
)


@dataclass
class TradeOpportunity:
    symbol: str
    score: float
    signal: str
    reason: str
    price: float
    change_pct: float
    sources: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class ScanResult:
    scanned_symbols: int
    evaluated_symbols: int
    opportunities: list[TradeOpportunity]
    buy_candidates: list[TradeOpportunity]
    sell_candidates: list[TradeOpportunity]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class MarketScanner:
    """Scan Robinhood discovery surfaces and rank trade opportunities."""

    def __init__(self, service: RobinhoodService, config: ScannerConfig) -> None:
        self.service = service
        self.config = config

    def discover_symbols(self) -> dict[str, list[str]]:
        """Collect candidate symbols from Robinhood lists, movers, and watchlists."""
        symbol_sources: dict[str, list[str]] = {}

        for tag in self.config.discovery_tags:
            try:
                symbols = self.service.get_tag_symbols(tag)
                symbol_sources[f"tag:{tag}"] = symbols
                logger.info("Tag %s returned %s symbols", tag, len(symbols))
            except Exception:
                logger.exception("Failed to load tag %s", tag)

        if self.config.include_movers:
            for direction in ("up", "down"):
                try:
                    movers = self.service.get_movers(direction)
                    symbols = [mover.symbol for mover in movers if mover.symbol]
                    symbol_sources[f"movers:{direction}"] = symbols
                    logger.info("Movers %s returned %s symbols", direction, len(symbols))
                except Exception:
                    logger.exception("Failed to load movers:%s", direction)

        if self.config.include_watchlists:
            try:
                for watchlist in self.service.get_watchlists():
                    if watchlist.symbols:
                        symbol_sources[f"watchlist:{watchlist.name}"] = watchlist.symbols
                        logger.info(
                            "Watchlist %s returned %s symbols",
                            watchlist.name,
                            len(watchlist.symbols),
                        )
            except Exception:
                logger.exception("Failed to load watchlists")

        return symbol_sources

    def _build_candidate_map(self, symbol_sources: dict[str, list[str]]) -> dict[str, list[str]]:
        candidates: dict[str, list[str]] = {}
        for source, symbols in symbol_sources.items():
            for symbol in symbols:
                key = symbol.upper()
                if not key:
                    continue
                candidates.setdefault(key, []).append(source)
        return candidates

    def _passes_liquidity_filters(
        self,
        symbol: str,
        quote,
        fundamentals: dict,
    ) -> bool:
        price = _safe_float(getattr(quote, "price", 0))
        if price < self.config.min_price_usd:
            return False

        avg_volume = _safe_float(fundamentals.get("average_volume"))
        if avg_volume and avg_volume < self.config.min_avg_volume:
            return False

        market_cap = _safe_float(fundamentals.get("market_cap"))
        if market_cap and market_cap < self.config.min_market_cap_usd:
            return False

        return True

    def _quick_score(
        self,
        symbol: str,
        quote,
        fundamentals: dict,
        sources: list[str],
    ) -> tuple[float, dict[str, float]]:
        change_pct = _safe_float(getattr(quote, "change_pct", 0))
        momentum = _clamp((change_pct + 5.0) / 10.0)

        volume = _safe_float(fundamentals.get("volume"))
        avg_volume = _safe_float(fundamentals.get("average_volume"), default=1.0)
        relative_volume = volume / avg_volume if avg_volume > 0 else 1.0
        volume_score = _clamp(relative_volume / 2.0)

        high_52 = _safe_float(fundamentals.get("high_52_weeks"))
        low_52 = _safe_float(fundamentals.get("low_52_weeks"))
        price = _safe_float(getattr(quote, "price", 0))
        range_position = 0.5
        if high_52 > low_52 > 0 and price > 0:
            range_position = _clamp((price - low_52) / (high_52 - low_52))
        # Favor names with room to run but not extreme blow-offs.
        range_score = 1.0 - abs(range_position - 0.65)

        popularity_boost = 0.0
        if any("popular" in source or "top-movers" in source for source in sources):
            popularity_boost = 0.15
        if any(source.startswith("movers:up") for source in sources):
            popularity_boost += 0.1

        pe_ratio = _safe_float(fundamentals.get("pe_ratio"))
        value_score = 0.5
        if pe_ratio > 0:
            if 5 <= pe_ratio <= 35:
                value_score = 0.8
            elif pe_ratio > 60:
                value_score = 0.2

        metrics = {
            "momentum": momentum,
            "volume": volume_score,
            "range": range_score,
            "value": value_score,
            "popularity_boost": popularity_boost,
            "change_pct": change_pct,
            "relative_volume": relative_volume,
        }

        score = (
            momentum * self.config.weights.momentum
            + volume_score * self.config.weights.volume
            + range_score * self.config.weights.range_position
            + value_score * self.config.weights.value
            + popularity_boost
        )
        return score, metrics

    def _analyst_score(self, symbol: str) -> float:
        try:
            rating = self.service.get_ratings(symbol)
            total = rating.num_buy + rating.num_hold + rating.num_sell
            if total <= 0:
                return 0.5
            buy_ratio = rating.num_buy / total
            sell_ratio = rating.num_sell / total
            return _clamp(0.5 + (buy_ratio - sell_ratio))
        except Exception:
            logger.debug("No analyst ratings for %s", symbol, exc_info=True)
            return 0.5

    def _strategy_bonus(self, symbol: str, strategy: Strategy) -> tuple[float, str, str]:
        decision = strategy.evaluate(symbol, self.service)
        if decision.signal == Signal.BUY:
            return 0.25, decision.signal.value, decision.reason
        if decision.signal == Signal.SELL:
            return -0.2, decision.signal.value, decision.reason
        return 0.0, decision.signal.value, decision.reason

    def scan(self, strategy: Strategy | None = None) -> ScanResult:
        symbol_sources = self.discover_symbols()
        candidate_map = self._build_candidate_map(symbol_sources)
        all_symbols = sorted(candidate_map.keys())[: self.config.max_candidates]

        logger.info("Discovered %s unique candidate symbols", len(candidate_map))
        quotes = self.service.get_quotes_batch(all_symbols)
        fundamentals = self.service.get_fundamentals_batch(all_symbols)

        screened: list[tuple[str, float, dict[str, float], list[str]]] = []
        for symbol in all_symbols:
            quote = quotes.get(symbol)
            if quote is None:
                continue
            fund = fundamentals.get(symbol, {})
            if not self._passes_liquidity_filters(symbol, quote, fund):
                continue
            score, metrics = self._quick_score(symbol, quote, fund, candidate_map[symbol])
            screened.append((symbol, score, metrics, candidate_map[symbol]))

        screened.sort(key=lambda item: item[1], reverse=True)
        deep_candidates = screened[: self.config.deep_scan_limit]

        opportunities: list[TradeOpportunity] = []
        for symbol, quick_score, metrics, sources in deep_candidates:
            quote = quotes[symbol]
            analyst_score = self._analyst_score(symbol)
            strategy_bonus = 0.0
            signal = "hold"
            reason = "Passed market screen"

            if strategy is not None:
                strategy_bonus, signal, reason = self._strategy_bonus(symbol, strategy)

            final_score = _clamp(
                quick_score * 0.55
                + analyst_score * self.config.weights.analyst
                + strategy_bonus
            )
            metrics = {
                **metrics,
                "quick_score": quick_score,
                "analyst_score": analyst_score,
                "strategy_bonus": strategy_bonus,
                "final_score": final_score,
            }

            if final_score < self.config.min_score and signal not in {Signal.BUY.value, Signal.SELL.value}:
                continue

            opportunities.append(
                TradeOpportunity(
                    symbol=symbol,
                    score=final_score,
                    signal=signal,
                    reason=reason,
                    price=_safe_float(quote.price),
                    change_pct=_safe_float(quote.change_pct),
                    sources=sources,
                    metrics=metrics,
                )
            )

        opportunities.sort(key=lambda item: item.score, reverse=True)
        buy_candidates = [o for o in opportunities if o.signal == Signal.BUY.value]
        sell_candidates = [o for o in opportunities if o.signal == Signal.SELL.value]

        if not buy_candidates:
            buy_candidates = [
                o for o in opportunities if o.score >= self.config.min_score
            ][: self.config.top_opportunities]

        return ScanResult(
            scanned_symbols=len(candidate_map),
            evaluated_symbols=len(deep_candidates),
            opportunities=opportunities[: self.config.top_opportunities],
            buy_candidates=buy_candidates[: self.config.top_opportunities],
            sell_candidates=sell_candidates[: self.config.top_opportunities],
        )
