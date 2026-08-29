from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from robinhood_bot.config import RiskConfig, TradingConfig
from robinhood_bot.portfolio.journal import TradeJournal


@dataclass
class RiskVerdict:
    allowed: bool
    reason: str


class RiskManager:
    """Pre-trade and position-level risk controls."""

    def __init__(self, config: RiskConfig, trading: TradingConfig, journal: TradeJournal) -> None:
        self.config = config
        self.trading = trading
        self.journal = journal

    def can_open_market(self, market_open: bool) -> RiskVerdict:
        if self.config.trade_only_during_market_hours and not market_open:
            return RiskVerdict(False, "Market is closed")
        return RiskVerdict(True, "Market hours OK")

    def can_trade_today(self) -> RiskVerdict:
        daily_pnl = self.journal.daily_realized_pnl(date.today())
        if daily_pnl <= -abs(self.config.max_daily_loss_usd):
            return RiskVerdict(
                False,
                f"Daily loss limit reached (${daily_pnl:,.2f})",
            )
        return RiskVerdict(True, "Within daily loss limit")

    def can_buy(
        self,
        *,
        symbol: str,
        open_positions: set[str],
        buying_power: float,
        trade_amount_usd: float,
        opportunity_score: float = 1.0,
    ) -> RiskVerdict:
        if symbol in open_positions:
            return RiskVerdict(False, "Already holding position")

        if len(open_positions) >= self.trading.max_positions:
            return RiskVerdict(False, "Max positions reached")

        if opportunity_score < self.config.min_opportunity_score:
            return RiskVerdict(
                False,
                f"Score {opportunity_score:.2f} below minimum {self.config.min_opportunity_score}",
            )

        max_trade = buying_power * self.trading.max_position_pct_of_buying_power
        if trade_amount_usd > max_trade:
            return RiskVerdict(
                False,
                f"Trade size ${trade_amount_usd:,.2f} exceeds {self.trading.max_position_pct_of_buying_power:.0%} of buying power",
            )

        if trade_amount_usd > buying_power:
            return RiskVerdict(False, "Insufficient buying power")

        return RiskVerdict(True, "Risk checks passed")

    def should_stop_out(self, *, pnl_pct: float) -> bool:
        return pnl_pct <= -abs(self.config.stop_loss_pct)

    def should_take_profit(self, *, pnl_pct: float) -> bool:
        return pnl_pct >= abs(self.config.take_profit_pct)
