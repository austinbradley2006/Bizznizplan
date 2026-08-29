from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from robinhood_bot.client import RobinhoodService
from robinhood_bot.config import AppConfig, load_config
from robinhood_bot.strategies import build_strategy
from robinhood_bot.strategies.base import Signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("robinhood_bot")


class TradingBot:
    def __init__(self, config: AppConfig, service: RobinhoodService) -> None:
        self.config = config
        self.service = service
        self.strategy = build_strategy(config.strategy.name, config.strategy.params)

    def run_once(self) -> list[dict]:
        results: list[dict] = []
        open_positions = {
            position["symbol"].upper()
            for position in self.service.account_snapshot(self.config.trading.symbols).positions
            if float(position["quantity"]) > 0
        }

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
                if symbol in open_positions:
                    result["action"] = "skipped_already_long"
                elif len(open_positions) >= self.config.trading.max_positions:
                    result["action"] = "skipped_max_positions"
                else:
                    result["action"] = self.service.buy_market(
                        symbol,
                        self.config.trading.trade_amount_usd,
                        dry_run=not self.config.can_place_orders,
                    )
                    if not result["action"].get("dry_run", True):
                        open_positions.add(symbol)

            elif decision.signal == Signal.SELL:
                quantity = self.service.get_position_quantity(symbol)
                if quantity <= 0:
                    result["action"] = "skipped_no_position"
                else:
                    result["action"] = self.service.sell_market(
                        symbol,
                        quantity,
                        dry_run=not self.config.can_place_orders,
                    )
                    open_positions.discard(symbol)

            else:
                result["action"] = "hold"

            results.append(result)

        return results

    def run_loop(self) -> None:
        logger.info(
            "Starting bot | strategy=%s | dry_run=%s | live=%s | symbols=%s",
            self.config.strategy.name,
            self.config.bot.dry_run,
            self.config.bot.live_trading_enabled,
            ",".join(self.config.trading.symbols),
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
    print("\nQuotes:")
    for symbol, price in snapshot.quotes.items():
        print(f"  {symbol}: ${price:,.2f}")
    print("\nPositions:")
    if not snapshot.positions:
        print("  (none)")
    for position in snapshot.positions:
        print(
            f"  {position['symbol']}: {position['quantity']} @ "
            f"${position['average_buy_price']:,.2f}"
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
