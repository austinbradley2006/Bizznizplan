from __future__ import annotations

from robinhood_bot.config import TradingConfig
from robinhood_bot.strategies.indicators import atr


class PositionSizer:
    """Calculate order size from config and optional volatility."""

    def __init__(self, config: TradingConfig) -> None:
        self.config = config

    def size_usd(
        self,
        *,
        buying_power: float,
        price: float,
        highs: list[float] | None = None,
        lows: list[float] | None = None,
        closes: list[float] | None = None,
    ) -> float:
        if self.config.sizing_mode == "percent_portfolio":
            amount = buying_power * self.config.portfolio_pct_per_trade
        elif (
            self.config.sizing_mode == "volatility"
            and highs
            and lows
            and closes
            and price > 0
        ):
            current_atr = atr(highs, lows, closes, self.config.atr_period)
            if current_atr and current_atr > 0:
                risk_budget = buying_power * self.config.risk_pct_per_trade
                shares_at_risk = risk_budget / (current_atr * self.config.atr_multiplier)
                amount = shares_at_risk * price
            else:
                amount = self.config.trade_amount_usd
        else:
            amount = self.config.trade_amount_usd

        amount = min(amount, buying_power * self.config.max_position_pct_of_buying_power)
        return round(max(amount, 0.0), 2)
