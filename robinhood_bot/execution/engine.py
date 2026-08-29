from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import AppConfig
from robinhood_bot.portfolio.journal import TradeJournal, TradeRecord
from robinhood_bot.risk.manager import RiskManager
from robinhood_bot.risk.position_sizer import PositionSizer
from robinhood_bot.scanner.models import TradeOpportunity

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    symbol: str
    side: str
    status: str
    detail: dict | str
    dry_run: bool


class ExecutionEngine:
    """Unified trade execution with risk checks and journaling."""

    def __init__(
        self,
        config: AppConfig,
        service: RobinhoodService,
        risk: RiskManager,
        journal: TradeJournal,
    ) -> None:
        self.config = config
        self.service = service
        self.risk = risk
        self.journal = journal
        self.sizer = PositionSizer(config.trading)

    def _log_trade(
        self,
        *,
        symbol: str,
        asset_type: str,
        side: str,
        quantity: float,
        price: float,
        reason: str,
        dry_run: bool,
        score: float | None,
    ) -> None:
        self.journal.record(
            TradeRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                symbol=symbol,
                asset_type=asset_type,
                side=side,
                quantity=quantity,
                price=price,
                notional=round(quantity * price, 2),
                reason=reason,
                dry_run=dry_run,
                score=score,
            )
        )

    def execute_stock_buy(
        self,
        opportunity: TradeOpportunity,
        *,
        open_positions: set[str],
        buying_power: float,
        market_open: bool,
    ) -> ExecutionResult:
        symbol = opportunity.symbol
        dry_run = not self.config.can_place_orders

        for check in (
            self.risk.can_trade_today(),
            self.risk.can_open_market(market_open),
            self.risk.can_buy(
                symbol=symbol,
                open_positions=open_positions,
                buying_power=buying_power,
                trade_amount_usd=self.config.trading.trade_amount_usd,
                opportunity_score=opportunity.score,
            ),
        ):
            if not check.allowed:
                return ExecutionResult(symbol, "buy", "blocked", check.reason, dry_run)

        bars = self.service.get_ohlc(symbol)
        amount = self.sizer.size_usd(
            buying_power=buying_power,
            price=opportunity.price or self.service.get_price(symbol),
            highs=bars.get("highs"),
            lows=bars.get("lows"),
            closes=bars.get("closes"),
        )
        if amount <= 0:
            return ExecutionResult(symbol, "buy", "blocked", "Zero position size", dry_run)

        action = self.service.buy_market(symbol, amount, dry_run=dry_run)
        if not action.get("dry_run", True):
            open_positions.add(symbol.upper())

        self._log_trade(
            symbol=symbol,
            asset_type="stock",
            side="buy",
            quantity=float(action.get("quantity", 0)),
            price=float(action.get("estimated_price", 0)),
            reason=opportunity.reason,
            dry_run=bool(action.get("dry_run", True)),
            score=opportunity.score,
        )
        return ExecutionResult(symbol, "buy", "executed", action, dry_run)

    def execute_stock_sell(
        self,
        symbol: str,
        *,
        reason: str,
        open_positions: set[str],
        score: float | None = None,
    ) -> ExecutionResult:
        dry_run = not self.config.can_place_orders
        quantity = self.service.get_position_quantity(symbol)
        if quantity <= 0:
            return ExecutionResult(symbol, "sell", "skipped", "No position", dry_run)

        price = self.service.get_price(symbol)
        action = self.service.sell_market(symbol, quantity, dry_run=dry_run)
        if not action.get("dry_run", True):
            open_positions.discard(symbol.upper())

        self._log_trade(
            symbol=symbol,
            asset_type="stock",
            side="sell",
            quantity=quantity,
            price=price,
            reason=reason,
            dry_run=bool(action.get("dry_run", True)),
            score=score,
        )
        return ExecutionResult(symbol, "sell", "executed", action, dry_run)

    def execute_crypto_buy(
        self,
        opportunity: TradeOpportunity,
        *,
        open_positions: set[str],
        buying_power: float,
    ) -> ExecutionResult:
        symbol = opportunity.symbol
        dry_run = not self.config.can_place_orders

        verdict = self.risk.can_buy(
            symbol=symbol,
            open_positions=open_positions,
            buying_power=buying_power,
            trade_amount_usd=self.config.trading.trade_amount_usd,
            opportunity_score=opportunity.score,
        )
        if not verdict.allowed:
            return ExecutionResult(symbol, "buy", "blocked", verdict.reason, dry_run)

        amount = min(
            self.config.trading.trade_amount_usd,
            buying_power * self.config.trading.max_position_pct_of_buying_power,
        )
        action = self.service.buy_crypto_market(symbol, amount, dry_run=dry_run)
        if not action.get("dry_run", True):
            open_positions.add(symbol.upper())

        self._log_trade(
            symbol=symbol,
            asset_type="crypto",
            side="buy",
            quantity=float(action.get("quantity", 0)),
            price=float(action.get("estimated_price", 0)),
            reason=opportunity.reason,
            dry_run=bool(action.get("dry_run", True)),
            score=opportunity.score,
        )
        return ExecutionResult(symbol, "buy", "executed", action, dry_run)

    def check_stop_losses(self, open_positions: set[str]) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        for symbol in sorted(open_positions):
            if self.service.is_crypto_symbol(symbol):
                continue
            pnl_pct = self.service.get_position_pnl_pct(symbol)
            if pnl_pct is None:
                continue
            if self.risk.should_stop_out(pnl_pct=pnl_pct):
                results.append(
                    self.execute_stock_sell(
                        symbol,
                        reason=f"Stop loss triggered at {pnl_pct:+.2f}%",
                        open_positions=open_positions,
                    )
                )
            elif self.risk.should_take_profit(pnl_pct=pnl_pct):
                results.append(
                    self.execute_stock_sell(
                        symbol,
                        reason=f"Take profit triggered at {pnl_pct:+.2f}%",
                        open_positions=open_positions,
                    )
                )
        return results
