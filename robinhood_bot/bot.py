from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from robinhood_bot.backtest import Backtester
from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import AppConfig, load_config
from robinhood_bot.execution import ExecutionEngine
from robinhood_bot.portfolio import TradeJournal
from robinhood_bot.risk import RiskManager
from robinhood_bot.scanner import (
    CryptoScanner,
    MarketScanner,
    OptionsScanner,
    ScanResult,
    TradeOpportunity,
)
from robinhood_bot.strategies import build_strategy
from robinhood_bot.strategies.base import Signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("robinhood_bot")


def _format_opportunity(opportunity: TradeOpportunity) -> str:
    sources = ", ".join(opportunity.sources[:3])
    if len(opportunity.sources) > 3:
        sources += ", ..."
    label = opportunity.display_symbol
    if opportunity.asset_type != "stock":
        label = f"[{opportunity.asset_type}] {label}"
    change = (
        f"chg={opportunity.change_pct:+.2f}%"
        if opportunity.asset_type != "option"
        else f"mark=${opportunity.price:,.2f}"
    )
    return (
        f"{label:24} score={opportunity.score:.2f} "
        f"signal={opportunity.signal:4} {change} | {opportunity.reason} "
        f"[{sources}]"
    )


def print_scan_results(result: ScanResult) -> None:
    print(f"Market: {result.market}")
    print(f"Scanned universe: {result.scanned_symbols} symbols")
    print(f"Deep evaluated: {result.evaluated_symbols} symbols")
    print(f"Top opportunities: {len(result.opportunities)}\n")

    if result.opportunities:
        print("Top ranked:")
        for opportunity in result.opportunities:
            print(f"  {_format_opportunity(opportunity)}")
    else:
        print("No opportunities met the score threshold.")

    if result.buy_candidates:
        print("\nBuy candidates:")
        for opportunity in result.buy_candidates:
            print(f"  {_format_opportunity(opportunity)}")

    if result.sell_candidates:
        print("\nSell candidates:")
        for opportunity in result.sell_candidates:
            print(f"  {_format_opportunity(opportunity)}")


class TradingBot:
    def __init__(self, config: AppConfig, service: RobinhoodService) -> None:
        self.config = config
        self.service = service
        self.strategy = build_strategy(config.strategy.name, config.strategy.params)
        self.journal = TradeJournal(config.risk.journal_path)
        self.risk = RiskManager(config.risk, config.trading, self.journal)
        self.executor = ExecutionEngine(config, service, self.risk, self.journal)
        self.scanner = MarketScanner(service, config.scanner)
        self.options_scanner = OptionsScanner(service, self.scanner, config.options_scanner)
        self.crypto_scanner = CryptoScanner(service, config.crypto_scanner)

    def scan_market(self) -> ScanResult:
        return self.scanner.scan(strategy=self.strategy)

    def scan_options(self) -> ScanResult:
        return self.options_scanner.scan(strategy=self.strategy)

    def scan_crypto(self) -> ScanResult:
        return self.crypto_scanner.scan(strategy=self.strategy)

    def scan_all(self) -> list[ScanResult]:
        results = [self.scan_market()]
        if self.config.options_scanner.enabled:
            results.append(self.scan_options())
        if self.config.crypto_scanner.enabled:
            results.append(self.scan_crypto())
        return results

    def _open_position_symbols(self) -> set[str]:
        positions = self.service.account_snapshot([]).positions
        return {
            position["symbol"].upper()
            for position in positions
            if float(position["quantity"]) > 0
        }

    def _evaluate_static_symbols(self, open_positions: set[str], buying_power: float, market_open: bool) -> list[dict]:
        results: list[dict] = []
        for symbol in self.config.trading.symbols:
            decision = self.strategy.evaluate(symbol, self.service)
            logger.info("%s signal=%s reason=%s", symbol, decision.signal.value, decision.reason)
            opportunity = TradeOpportunity(
                symbol=symbol,
                score=decision.confidence,
                signal=decision.signal.value,
                reason=decision.reason,
                price=self.service.get_price(symbol),
            )
            if decision.signal == Signal.BUY:
                execution = self.executor.execute_stock_buy(
                    opportunity,
                    open_positions=open_positions,
                    buying_power=buying_power,
                    market_open=market_open,
                )
            elif decision.signal == Signal.SELL:
                execution = self.executor.execute_stock_sell(
                    symbol,
                    reason=decision.reason,
                    open_positions=open_positions,
                    score=decision.confidence,
                )
            else:
                execution = None
            results.append(
                {
                    "symbol": symbol,
                    "signal": decision.signal.value,
                    "reason": decision.reason,
                    "execution": execution,
                }
            )
        return results

    def _evaluate_scanner(self, open_positions: set[str], buying_power: float, market_open: bool) -> list[dict]:
        results: list[dict] = []
        stop_results = self.executor.check_stop_losses(open_positions)
        results.extend({"type": "risk", "execution": item} for item in stop_results)

        stock_scan = self.scan_market()
        for opportunity in stock_scan.sell_candidates:
            if opportunity.asset_type != "stock":
                continue
            execution = self.executor.execute_stock_sell(
                opportunity.symbol,
                reason=opportunity.reason,
                open_positions=open_positions,
                score=opportunity.score,
            )
            results.append({"type": "stock", "opportunity": opportunity, "execution": execution})

        for opportunity in stock_scan.buy_candidates:
            if opportunity.asset_type != "stock":
                continue
            execution = self.executor.execute_stock_buy(
                opportunity,
                open_positions=open_positions,
                buying_power=buying_power,
                market_open=market_open,
            )
            results.append({"type": "stock", "opportunity": opportunity, "execution": execution})

        if self.config.crypto_scanner.enabled and self.service.crypto_available():
            crypto_scan = self.scan_crypto()
            for opportunity in crypto_scan.buy_candidates[:3]:
                execution = self.executor.execute_crypto_buy(
                    opportunity,
                    open_positions=open_positions,
                    buying_power=buying_power,
                )
                results.append({"type": "crypto", "opportunity": opportunity, "execution": execution})

        for symbol in sorted(open_positions):
            if self.service.is_crypto_symbol(symbol):
                continue
            decision = self.strategy.evaluate(symbol, self.service)
            if decision.signal != Signal.SELL:
                continue
            execution = self.executor.execute_stock_sell(
                symbol,
                reason=decision.reason,
                open_positions=open_positions,
                score=decision.confidence,
            )
            results.append({"type": "position_exit", "symbol": symbol, "execution": execution})

        return results

    def run_once(self) -> list[dict]:
        snapshot = self.service.account_snapshot([])
        open_positions = self._open_position_symbols()
        market_open = self.service.is_market_open()

        if self.config.scanner.enabled and self.config.scanner.symbol_source == "scanner":
            return self._evaluate_scanner(open_positions, snapshot.buying_power, market_open)

        return self._evaluate_static_symbols(open_positions, snapshot.buying_power, market_open)

    def run_loop(self) -> None:
        mode = (
            "scanner"
            if self.config.scanner.enabled and self.config.scanner.symbol_source == "scanner"
            else "static"
        )
        logger.info(
            "Starting bot | mode=%s | strategy=%s | dry_run=%s | live=%s",
            mode,
            self.config.strategy.name,
            self.config.bot.dry_run,
            self.config.bot.live_trading_enabled,
        )

        if self.config.can_place_orders:
            logger.warning("LIVE TRADING IS ENABLED. Real orders will be sent to Robinhood.")

        while True:
            started = datetime.now(timezone.utc).isoformat()
            logger.info("Evaluation cycle started at %s", started)
            try:
                results = self.run_once()
                logger.info("Cycle completed with %s actions", len(results))
            except Exception:
                logger.exception("Evaluation cycle failed")
            logger.info("Sleeping %s seconds", self.config.bot.poll_interval_seconds)
            time.sleep(self.config.bot.poll_interval_seconds)


def cmd_status(config: AppConfig, service: RobinhoodService, journal: TradeJournal) -> int:
    snapshot = service.account_snapshot(config.trading.symbols)
    print(f"Buying power: ${snapshot.buying_power:,.2f}")
    print(f"Market open: {service.is_market_open()}")
    print(f"Dry run: {config.bot.dry_run}")
    print(f"Live trading enabled: {config.bot.live_trading_enabled}")
    print(f"Strategy: {config.strategy.name}")
    print(f"Stock scanner: {config.scanner.enabled} ({config.scanner.symbol_source})")
    print(f"Options scanner: {config.options_scanner.enabled}")
    print(f"Crypto scanner: {config.crypto_scanner.enabled} (available: {service.crypto_available()})")
    print(f"Risk | stop-loss: {config.risk.stop_loss_pct}% | take-profit: {config.risk.take_profit_pct}%")
    print(f"Risk | max daily loss: ${config.risk.max_daily_loss_usd:,.2f}")
    print("\nPositions:")
    if not snapshot.positions:
        print("  (none)")
    for position in snapshot.positions:
        pnl = service.get_position_pnl_pct(position["symbol"])
        pnl_text = f" | P&L {pnl:+.2f}%" if pnl is not None else ""
        print(
            f"  {position['symbol']}: {position['quantity']} @ "
            f"${position['average_buy_price']:,.2f}{pnl_text}"
        )

    recent = journal.recent_trades(5)
    if recent:
        print("\nRecent trades:")
        for trade in recent:
            print(
                f"  {trade['timestamp'][:19]} {trade['side']:4} "
                f"{trade['symbol']:8} ${trade['notional']:,.2f} "
                f"({'dry-run' if trade.get('dry_run') else 'live'})"
            )
    return 0


def cmd_journal(journal: TradeJournal) -> int:
    trades = journal.recent_trades(50)
    if not trades:
        print("No trades recorded yet.")
        return 0
    for trade in trades:
        print(
            f"{trade['timestamp'][:19]} | {trade['asset_type']:6} | {trade['side']:4} | "
            f"{trade['symbol']:10} | qty={trade['quantity']} | ${trade['notional']:,.2f} | "
            f"{trade['reason'][:60]}"
        )
    return 0


def cmd_backtest(config: AppConfig, service: RobinhoodService, symbols: list[str]) -> int:
    strategy = build_strategy(config.strategy.name, config.strategy.params)
    backtester = Backtester(strategy)
    for symbol in symbols:
        closes = service.get_closes(symbol, span="year", interval="day")
        if len(closes) < 40:
            print(f"{symbol}: insufficient history ({len(closes)} bars)")
            continue
        result = backtester.run_on_closes(symbol, closes)
        win_rate = (result.wins / result.trades * 100) if result.trades else 0
        print(
            f"{symbol:6} | return {result.total_return_pct:+6.2f}% | "
            f"trades {result.trades:3} | win rate {win_rate:5.1f}% | "
            f"max DD {result.max_drawdown_pct:.2f}%"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Robinhood trading bot")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config (default: config.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show account snapshot and bot settings")
    subparsers.add_parser("journal", help="Show recent trade journal entries")
    subparsers.add_parser("scan", help="Scan stocks for ranked opportunities")
    subparsers.add_parser("scan-options", help="Scan option chains on active underlyings")
    subparsers.add_parser("scan-crypto", help="Scan Robinhood crypto pairs")
    subparsers.add_parser("scan-all", help="Scan stocks, options, and crypto")
    subparsers.add_parser("once", help="Run one evaluation cycle")
    subparsers.add_parser("run", help="Run the bot loop continuously")

    backtest_parser = subparsers.add_parser("backtest", help="Backtest strategy on historical data")
    backtest_parser.add_argument(
        "symbols",
        nargs="*",
        default=["AAPL", "MSFT", "NVDA"],
        help="Symbols to backtest",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)

    service = RobinhoodService()
    try:
        service.connect()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    bot = TradingBot(config, service)
    journal = TradeJournal(config.risk.journal_path)

    if args.command == "status":
        return cmd_status(config, service, journal)
    if args.command == "journal":
        return cmd_journal(journal)
    if args.command == "scan":
        print_scan_results(bot.scan_market())
        return 0
    if args.command == "scan-options":
        print_scan_results(bot.scan_options())
        return 0
    if args.command == "scan-crypto":
        print_scan_results(bot.scan_crypto())
        return 0
    if args.command == "scan-all":
        for index, result in enumerate(bot.scan_all()):
            if index > 0:
                print("\n" + "=" * 72 + "\n")
            print_scan_results(result)
        return 0
    if args.command == "backtest":
        return cmd_backtest(config, service, [s.upper() for s in args.symbols])
    if args.command == "once":
        bot.run_once()
        return 0
    if args.command == "run":
        bot.run_loop()
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
