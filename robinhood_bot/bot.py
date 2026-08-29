from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import AppConfig, load_config
from robinhood_bot.scanner import MarketScanner, ScanResult, TradeOpportunity
from robinhood_bot.strategies import build_strategy
from robinhood_bot.strategies.base import Signal, Strategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("robinhood_bot")


def _format_opportunity(opportunity: TradeOpportunity) -> str:
    sources = ", ".join(opportunity.sources[:3])
    if len(opportunity.sources) > 3:
        sources += ", ..."
    return (
        f"{opportunity.symbol:6} score={opportunity.score:.2f} "
        f"signal={opportunity.signal:4} price=${opportunity.price:,.2f} "
        f"chg={opportunity.change_pct:+.2f}% | {opportunity.reason} "
        f"[{sources}]"
    )


def print_scan_results(result: ScanResult) -> None:
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
        self.scanner = MarketScanner(service, config.scanner)

    def scan_market(self) -> ScanResult:
        return self.scanner.scan(strategy=self.strategy)

    def _open_position_symbols(self) -> set[str]:
        positions = self.service.account_snapshot([]).positions
        return {
            position["symbol"].upper()
            for position in positions
            if float(position["quantity"]) > 0
        }

    def _execute_buy(self, symbol: str, open_positions: set[str]) -> dict | str:
        if symbol in open_positions:
            return "skipped_already_long"
        if len(open_positions) >= self.config.trading.max_positions:
            return "skipped_max_positions"
        action = self.service.buy_market(
            symbol,
            self.config.trading.trade_amount_usd,
            dry_run=not self.config.can_place_orders,
        )
        if not action.get("dry_run", True):
            open_positions.add(symbol)
        return action

    def _execute_sell(self, symbol: str, open_positions: set[str]) -> dict | str:
        quantity = self.service.get_position_quantity(symbol)
        if quantity <= 0:
            return "skipped_no_position"
        action = self.service.sell_market(
            symbol,
            quantity,
            dry_run=not self.config.can_place_orders,
        )
        if not action.get("dry_run", True):
            open_positions.discard(symbol)
        return action

    def _evaluate_static_symbols(self, open_positions: set[str]) -> list[dict]:
        results: list[dict] = []
        for symbol in self.config.trading.symbols:
            decision = self.strategy.evaluate(symbol, self.service)
            logger.info("%s signal=%s reason=%s", symbol, decision.signal.value, decision.reason)

            result = {
                "symbol": symbol,
                "signal": decision.signal.value,
                "reason": decision.reason,
                "action": None,
            }

            if decision.signal == Signal.BUY:
                result["action"] = self._execute_buy(symbol, open_positions)
            elif decision.signal == Signal.SELL:
                result["action"] = self._execute_sell(symbol, open_positions)
            else:
                result["action"] = "hold"

            results.append(result)
        return results

    def _evaluate_scanner(self, open_positions: set[str]) -> list[dict]:
        scan_result = self.scan_market()
        results: list[dict] = []

        for opportunity in scan_result.sell_candidates:
            logger.info(
                "Scanner sell %s score=%.2f reason=%s",
                opportunity.symbol,
                opportunity.score,
                opportunity.reason,
            )
            results.append(
                {
                    "symbol": opportunity.symbol,
                    "signal": Signal.SELL.value,
                    "reason": opportunity.reason,
                    "score": opportunity.score,
                    "action": self._execute_sell(opportunity.symbol, open_positions),
                }
            )

        for opportunity in scan_result.buy_candidates:
            logger.info(
                "Scanner buy %s score=%.2f reason=%s",
                opportunity.symbol,
                opportunity.score,
                opportunity.reason,
            )
            results.append(
                {
                    "symbol": opportunity.symbol,
                    "signal": Signal.BUY.value,
                    "reason": opportunity.reason,
                    "score": opportunity.score,
                    "action": self._execute_buy(opportunity.symbol, open_positions),
                }
            )

        for symbol in sorted(open_positions):
            if any(item["symbol"] == symbol and item["signal"] == Signal.SELL.value for item in results):
                continue
            decision = self.strategy.evaluate(symbol, self.service)
            if decision.signal != Signal.SELL:
                continue
            logger.info("Held position sell %s reason=%s", symbol, decision.reason)
            results.append(
                {
                    "symbol": symbol,
                    "signal": Signal.SELL.value,
                    "reason": decision.reason,
                    "action": self._execute_sell(symbol, open_positions),
                }
            )

        return results

    def run_once(self) -> list[dict]:
        open_positions = self._open_position_symbols()

        if self.config.scanner.enabled and self.config.scanner.symbol_source == "scanner":
            return self._evaluate_scanner(open_positions)

        return self._evaluate_static_symbols(open_positions)

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
                self.run_once()
            except Exception:
                logger.exception("Evaluation cycle failed")
            logger.info("Sleeping %s seconds", self.config.bot.poll_interval_seconds)
            time.sleep(self.config.bot.poll_interval_seconds)


def cmd_status(config: AppConfig, service: RobinhoodService) -> int:
    snapshot = service.account_snapshot(config.trading.symbols)
    print(f"Buying power: ${snapshot.buying_power:,.2f}")
    print(f"Dry run: {config.bot.dry_run}")
    print(f"Live trading enabled: {config.bot.live_trading_enabled}")
    print(f"Strategy: {config.strategy.name}")
    print(f"Scanner enabled: {config.scanner.enabled}")
    print(f"Symbol source: {config.scanner.symbol_source}")
    print("\nPositions:")
    if not snapshot.positions:
        print("  (none)")
    for position in snapshot.positions:
        print(
            f"  {position['symbol']}: {position['quantity']} @ "
            f"${position['average_buy_price']:,.2f}"
        )
    return 0


def cmd_scan(config: AppConfig, bot: TradingBot) -> int:
    result = bot.scan_market()
    print_scan_results(result)
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
    subparsers.add_parser("scan", help="Scan Robinhood for ranked trade opportunities")
    subparsers.add_parser("once", help="Run one evaluation cycle")
    subparsers.add_parser("run", help="Run the bot loop continuously")
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

    if args.command == "status":
        return cmd_status(config, service)
    if args.command == "scan":
        return cmd_scan(config, bot)
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
