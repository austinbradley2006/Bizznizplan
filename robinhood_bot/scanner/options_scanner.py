from __future__ import annotations

import logging

from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import OptionsScannerConfig
from robinhood_bot.scanner.market_scanner import MarketScanner
from robinhood_bot.scanner.models import ScanResult, TradeOpportunity
from robinhood_bot.strategies.base import Signal, Strategy

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class OptionsScanner:
    """Scan option chains on active underlyings for high-conviction setups."""

    def __init__(
        self,
        service: RobinhoodService,
        stock_scanner: MarketScanner,
        config: OptionsScannerConfig,
    ) -> None:
        self.service = service
        self.stock_scanner = stock_scanner
        self.config = config

    def _resolve_underlyings(self, strategy: Strategy | None) -> list[str]:
        if self.config.underlying_symbols:
            return [symbol.upper() for symbol in self.config.underlying_symbols]

        stock_scan = self.stock_scanner.scan(strategy=strategy)
        symbols = [item.symbol for item in stock_scan.opportunities]
        if not symbols:
            symbols = [item.symbol for item in stock_scan.buy_candidates]
        return symbols[: self.config.max_underlyings]

    def _score_contract(self, contract, underlying_price: float, direction: str) -> tuple[float, str]:
        volume = int(contract.volume or 0)
        open_interest = int(contract.open_interest or 0)
        delta = abs(float(contract.delta or 0))
        iv = float(contract.iv or 0)
        mark = float(contract.mark or 0)

        if volume < self.config.min_option_volume or open_interest < self.config.min_open_interest:
            return 0.0, "Low liquidity"

        liquidity_score = _clamp(volume / 1000) * 0.35 + _clamp(open_interest / 5000) * 0.35
        delta_score = 0.0
        if self.config.target_delta_min <= delta <= self.config.target_delta_max:
            delta_score = 0.2
        iv_score = 0.1 if 0.15 <= iv <= 0.8 else 0.0

        moneyness_bonus = 0.0
        strike = float(contract.strike)
        if underlying_price > 0:
            distance_pct = abs(strike - underlying_price) / underlying_price
            if distance_pct <= 0.05:
                moneyness_bonus = 0.1

        score = liquidity_score + delta_score + iv_score + moneyness_bonus
        reason = (
            f"{direction} {contract.option_type} vol={volume} oi={open_interest} "
            f"delta={delta:.2f} iv={iv:.2f} mark=${mark:.2f}"
        )
        return score, reason

    def scan(self, strategy: Strategy | None = None) -> ScanResult:
        underlyings = self._resolve_underlyings(strategy)
        opportunities: list[TradeOpportunity] = []

        for symbol in underlyings:
            try:
                underlying_price = self.service.get_price(symbol)
                expirations = self.service.get_options_expirations(symbol)
                if not expirations:
                    continue

                expiration = expirations[0]
                chain = self.service.get_options_chain(symbol, expiration)
                stock_signal = "hold"
                stock_reason = "Options scan"
                if strategy is not None:
                    decision = strategy.evaluate(symbol, self.service)
                    stock_signal = decision.signal.value
                    stock_reason = decision.reason

                contract_sets: list[tuple[str, list]] = []
                if stock_signal in {Signal.BUY.value, "hold"}:
                    contract_sets.append(("call", chain.calls))
                if stock_signal in {Signal.SELL.value, "hold"}:
                    contract_sets.append(("put", chain.puts))

                for side, contracts in contract_sets:
                    for contract in contracts:
                        score, reason = self._score_contract(contract, underlying_price, side)
                        if score < self.config.min_score:
                            continue

                        signal = Signal.BUY.value if side == "call" else Signal.SELL.value
                        if stock_signal == Signal.BUY.value and side == "call":
                            score += 0.1
                        if stock_signal == Signal.SELL.value and side == "put":
                            score += 0.1

                        opportunities.append(
                            TradeOpportunity(
                                symbol=symbol,
                                asset_type="option",
                                score=_clamp(score),
                                signal=signal,
                                reason=f"{stock_reason} | {reason}",
                                price=float(contract.mark or 0),
                                change_pct=0.0,
                                sources=[f"options:{expiration}"],
                                metrics={
                                    "volume": float(contract.volume or 0),
                                    "open_interest": float(contract.open_interest or 0),
                                    "delta": float(contract.delta or 0),
                                    "iv": float(contract.iv or 0),
                                },
                                contract={
                                    "strike": float(contract.strike),
                                    "expiration": contract.expiration,
                                    "option_type": contract.option_type,
                                    "option_id": contract.option_id,
                                    "underlying_price": underlying_price,
                                },
                            )
                        )
            except Exception:
                logger.exception("Failed options scan for %s", symbol)

        opportunities.sort(key=lambda item: item.score, reverse=True)
        top = opportunities[: self.config.top_opportunities]
        buy_candidates = [item for item in top if item.signal == Signal.BUY.value]
        sell_candidates = [item for item in top if item.signal == Signal.SELL.value]

        return ScanResult(
            market="options",
            scanned_symbols=len(underlyings),
            evaluated_symbols=len(underlyings),
            opportunities=top,
            buy_candidates=buy_candidates,
            sell_candidates=sell_candidates,
        )
