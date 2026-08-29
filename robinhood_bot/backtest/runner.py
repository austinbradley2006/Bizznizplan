from __future__ import annotations

from dataclasses import dataclass

from robinhood_bot.strategies.base import Signal, Strategy, StrategyDecision
from robinhood_bot.strategies.indicators import rsi, sma


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    trades: int
    wins: int
    losses: int
    total_return_pct: float
    max_drawdown_pct: float


class Backtester:
    """Simple walk-forward backtest on historical closes."""

    def __init__(self, strategy: Strategy, initial_capital: float = 10_000.0) -> None:
        self.strategy = strategy
        self.initial_capital = initial_capital

    def run_on_closes(self, symbol: str, closes: list[float]) -> BacktestResult:
        cash = self.initial_capital
        shares = 0.0
        entry_price = 0.0
        trades = 0
        wins = 0
        losses = 0
        peak_equity = self.initial_capital
        max_drawdown = 0.0

        class _CloseService:
            def get_closes(self, _symbol: str, *, span: str = "month", interval: str = "day") -> list[float]:
                return closes[: self._index + 1]

            def __init__(self) -> None:
                self._index = 0

        service = _CloseService()

        for index in range(30, len(closes)):
            service._index = index
            price = closes[index]
            decision = self._signal_from_closes(closes[: index + 1])

            if decision.signal == Signal.BUY and shares == 0 and cash > 0:
                shares = cash / price
                entry_price = price
                cash = 0.0
                trades += 1
            elif decision.signal == Signal.SELL and shares > 0:
                cash = shares * price
                pnl = (price - entry_price) / entry_price if entry_price else 0
                if pnl >= 0:
                    wins += 1
                else:
                    losses += 1
                shares = 0.0
                entry_price = 0.0
                trades += 1

            equity = cash + shares * price
            peak_equity = max(peak_equity, equity)
            if peak_equity > 0:
                drawdown = (peak_equity - equity) / peak_equity * 100
                max_drawdown = max(max_drawdown, drawdown)

        final_price = closes[-1]
        final_equity = cash + shares * final_price
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        return BacktestResult(
            symbol=symbol,
            strategy=self.strategy.name,
            trades=trades,
            wins=wins,
            losses=losses,
            total_return_pct=round(total_return, 2),
            max_drawdown_pct=round(max_drawdown, 2),
        )

    def _signal_from_closes(self, closes: list[float]) -> StrategyDecision:
        if self.strategy.name == "rsi":
            current = rsi(closes, 14)
            if current is None:
                return StrategyDecision(Signal.HOLD, "No RSI")
            if current <= 30:
                return StrategyDecision(Signal.BUY, f"RSI {current:.1f}")
            if current >= 70:
                return StrategyDecision(Signal.SELL, f"RSI {current:.1f}")
            return StrategyDecision(Signal.HOLD, f"RSI {current:.1f}")

        if self.strategy.name == "sma_crossover":
            fast = sma(closes, 10)
            slow = sma(closes, 30)
            if fast is None or slow is None:
                return StrategyDecision(Signal.HOLD, "No SMA")
            if fast > slow:
                return StrategyDecision(Signal.BUY, "Fast above slow")
            if fast < slow:
                return StrategyDecision(Signal.SELL, "Fast below slow")
            return StrategyDecision(Signal.HOLD, "SMA flat")

        return StrategyDecision(Signal.HOLD, "Unsupported in quick backtest")
