from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robinhood_bot.bot import TradingBot
    from robinhood_bot.client import RobinhoodService
    from robinhood_bot.config import AppConfig
    from robinhood_bot.portfolio.journal import TradeJournal

logger = logging.getLogger(__name__)

HELP_TEXT = """Robinhood Bot commands:

STATUS - account & positions
SCAN - top stock picks
SCAN ALL - stocks, options, crypto
ONCE - run one trading cycle
JOURNAL - recent trades
HELP - this message

Tips: commands are case-insensitive. Bot defaults to dry-run unless live trading is enabled in config."""


def handle_message(
    text: str,
    *,
    bot: "TradingBot",
    config: "AppConfig",
    service: "RobinhoodService",
    journal: "TradeJournal",
) -> str:
    command = text.strip().upper()
    if not command:
        return "Send HELP for available commands."

    if command in {"HELP", "?", "COMMANDS"}:
        return HELP_TEXT

    if command == "STATUS":
        return _format_status(config, service, journal)

    if command == "SCAN":
        return _format_scan(bot.scan_market(), limit=5)

    if command in {"SCAN ALL", "SCANALL", "SCAN-ALL"}:
        parts = [_format_scan(result, limit=3) for result in bot.scan_all()]
        return "\n\n".join(parts)

    if command == "ONCE":
        try:
            results = bot.run_once()
            return f"Cycle complete. {len(results)} action(s) taken. Check journal for details."
        except Exception as exc:
            logger.exception("ONCE command failed")
            return f"Cycle failed: {exc}"

    if command == "JOURNAL":
        return _format_journal(journal)

    if command in {"POSITIONS", "POS"}:
        return _format_positions(service)

    return f"Unknown command: {text}\n\n{HELP_TEXT}"


def _format_status(config: AppConfig, service: RobinhoodService, journal: TradeJournal) -> str:
    snapshot = service.account_snapshot([])
    lines = [
        f"Buying power: ${snapshot.buying_power:,.2f}",
        f"Market open: {service.is_market_open()}",
        f"Strategy: {config.strategy.name}",
        f"Dry run: {config.bot.dry_run}",
        f"Live: {config.bot.live_trading_enabled}",
    ]
    if snapshot.positions:
        lines.append("Positions:")
        for position in snapshot.positions[:8]:
            pnl = service.get_position_pnl_pct(position["symbol"])
            pnl_text = f" ({pnl:+.1f}%)" if pnl is not None else ""
            lines.append(
                f"  {position['symbol']} x{position['quantity']} @ ${position['average_buy_price']:,.2f}{pnl_text}"
            )
    else:
        lines.append("Positions: none")

    recent = journal.recent_trades(2)
    if recent:
        lines.append(f"Last trade: {recent[-1]['side']} {recent[-1]['symbol']}")
    return "\n".join(lines)


def _format_scan(result, *, limit: int) -> str:
    lines = [f"[{result.market.upper()}] Top picks:"]
    if not result.opportunities:
        lines.append("  No opportunities found.")
        return "\n".join(lines)
    for opportunity in result.opportunities[:limit]:
        label = opportunity.display_symbol
        lines.append(
            f"  {label} {opportunity.signal} score={opportunity.score:.2f} ${opportunity.price:,.2f}"
        )
    return "\n".join(lines)


def _format_journal(journal: TradeJournal) -> str:
    trades = journal.recent_trades(5)
    if not trades:
        return "No trades in journal yet."
    lines = ["Recent trades:"]
    for trade in trades:
        mode = "sim" if trade.get("dry_run") else "LIVE"
        lines.append(
            f"  {trade['side'].upper()} {trade['symbol']} ${trade['notional']:,.0f} ({mode})"
        )
    return "\n".join(lines)


def _format_positions(service: RobinhoodService) -> str:
    snapshot = service.account_snapshot([])
    if not snapshot.positions:
        return "No open positions."
    lines = ["Open positions:"]
    for position in snapshot.positions:
        pnl = service.get_position_pnl_pct(position["symbol"])
        pnl_text = f" P&L {pnl:+.1f}%" if pnl is not None else ""
        lines.append(
            f"  {position['symbol']}: {position['quantity']} @ ${position['average_buy_price']:,.2f}{pnl_text}"
        )
    return "\n".join(lines)
