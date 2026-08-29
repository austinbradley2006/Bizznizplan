from unittest.mock import MagicMock

import pytest

from robinhood_bot.backtest import Backtester
from robinhood_bot.client import RobinhoodService
from robinhood_bot.risk.manager import RiskManager
from robinhood_bot.config import RiskConfig, TradingConfig
from robinhood_bot.portfolio.journal import TradeJournal
from robinhood_bot.strategies.indicators import atr, bollinger_bands, macd, rsi, sma
from robinhood_bot.strategies.rsi import RSIStrategy


def test_sma_basic():
    values = list(range(1, 21))
    assert sma(values, 5) == 18.0


def test_rsi_bounds():
    rising = [float(i) for i in range(1, 40)]
    result = rsi(rising, 14)
    assert result is not None
    assert result > 50

    falling = [40.0 - i for i in range(40)]
    result = rsi(falling, 14)
    assert result is not None
    assert result < 50


def test_macd_returns_tuple():
    values = [100 + i * 0.5 + (i % 3) for i in range(60)]
    macd_line, signal_line, histogram = macd(values)
    assert macd_line is not None
    assert signal_line is not None
    assert histogram is not None


def test_bollinger_bands_order():
    values = [100.0] * 25
    lower, middle, upper = bollinger_bands(values, 20)
    assert lower is not None and middle is not None and upper is not None
    assert lower <= middle <= upper


def test_atr_positive():
    highs = [i + 2 for i in range(30)]
    lows = [i - 2 for i in range(30)]
    closes = [float(i) for i in range(30)]
    result = atr(highs, lows, closes, 14)
    assert result is not None
    assert result > 0


def test_risk_manager_blocks_max_positions(tmp_path):
    journal = TradeJournal(str(tmp_path / "trades.jsonl"))
    risk = RiskManager(RiskConfig(), TradingConfig(max_positions=2), journal)
    verdict = risk.can_buy(
        symbol="AAPL",
        open_positions={"MSFT", "NVDA"},
        buying_power=1000,
        trade_amount_usd=50,
        opportunity_score=0.9,
    )
    assert not verdict.allowed


def test_risk_manager_stop_loss():
    journal = TradeJournal("data/test-trades.jsonl")
    risk = RiskManager(RiskConfig(stop_loss_pct=8), TradingConfig(), journal)
    assert risk.should_stop_out(pnl_pct=-9.0)
    assert not risk.should_stop_out(pnl_pct=-3.0)


def test_account_snapshot_reads_pyhood_average_cost():
    """pyhood Position exposes average_cost; the snapshot must map it correctly."""
    position = MagicMock()
    position.symbol = "AAPL"
    position.quantity = 3.0
    position.average_cost = 150.0
    del position.average_buy_price  # ensure we never read the old attribute name

    quote = MagicMock()
    quote.price = 170.0

    client = MagicMock()
    client.get_buying_power.return_value = 1000.0
    client.get_positions.return_value = [position]
    client.get_quote.return_value = quote

    service = RobinhoodService()
    service._client = client

    snapshot = service.account_snapshot(["AAPL"])
    assert snapshot.positions[0]["average_buy_price"] == 150.0
    assert round(service.get_position_pnl_pct("AAPL"), 2) == 13.33


def test_backtest_runs():
    closes = [100 + (i % 7) - 3 for i in range(120)]
    strategy = RSIStrategy()
    result = Backtester(strategy).run_on_closes("TEST", closes)
    assert result.symbol == "TEST"
    assert result.trades >= 0
