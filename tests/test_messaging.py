from unittest.mock import MagicMock

from robinhood_bot.messaging.commands import handle_message
from robinhood_bot.scanner.models import ScanResult, TradeOpportunity


def _scan_result(market: str) -> ScanResult:
    return ScanResult(
        market=market,
        scanned_symbols=1,
        evaluated_symbols=1,
        opportunities=[
            TradeOpportunity(symbol="AAPL", score=0.7, signal="buy", reason="r", price=170.0)
        ],
        buy_candidates=[],
        sell_candidates=[],
    )


def test_help_command():
    reply = handle_message(
        "help",
        bot=MagicMock(),
        config=MagicMock(),
        service=MagicMock(),
        journal=MagicMock(),
    )
    assert "STATUS" in reply
    assert "SCAN" in reply


def test_unknown_command():
    reply = handle_message(
        "foobar",
        bot=MagicMock(),
        config=MagicMock(),
        service=MagicMock(),
        journal=MagicMock(),
    )
    assert "Unknown command" in reply


def test_scan_options_and_crypto_commands():
    bot = MagicMock()
    bot.scan_options.return_value = _scan_result("options")
    bot.scan_crypto.return_value = _scan_result("crypto")
    ctx = dict(config=MagicMock(), service=MagicMock(), journal=MagicMock())

    options_reply = handle_message("SCAN OPTIONS", bot=bot, **ctx)
    assert "OPTIONS" in options_reply
    bot.scan_options.assert_called_once()

    crypto_reply = handle_message("scan crypto", bot=bot, **ctx)
    assert "CRYPTO" in crypto_reply
    bot.scan_crypto.assert_called_once()


def test_backtest_command():
    from robinhood_bot.strategies.rsi import RSIStrategy

    bot = MagicMock()
    bot.strategy = RSIStrategy()
    bot.service.get_closes.return_value = [100 + (i % 7) - 3 for i in range(120)]

    reply = handle_message(
        "BACKTEST AAPL",
        bot=bot,
        config=MagicMock(),
        service=MagicMock(),
        journal=MagicMock(),
    )
    assert "Backtest" in reply
    assert "AAPL" in reply
