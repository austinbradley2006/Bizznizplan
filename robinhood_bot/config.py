from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class BotConfig:
    poll_interval_seconds: int = 300
    dry_run: bool = True
    live_trading_enabled: bool = False


@dataclass
class TradingConfig:
    symbols: list[str] = field(default_factory=lambda: ["AAPL"])
    trade_amount_usd: float = 50.0
    max_positions: int = 5


@dataclass
class StrategyConfig:
    name: str = "sma_crossover"
    params: dict = field(default_factory=dict)


@dataclass
class ScannerWeights:
    momentum: float = 0.25
    volume: float = 0.2
    range_position: float = 0.15
    value: float = 0.1
    analyst: float = 0.2


@dataclass
class ScannerConfig:
    enabled: bool = True
    # static = use trading.symbols; scanner = discover opportunities across Robinhood
    symbol_source: str = "scanner"
    discovery_tags: list[str] = field(
        default_factory=lambda: [
            "100-most-popular",
            "10-most-popular",
            "top-movers",
        ]
    )
    include_movers: bool = True
    include_watchlists: bool = True
    min_price_usd: float = 5.0
    min_avg_volume: float = 100_000.0
    min_market_cap_usd: float = 500_000_000.0
    max_candidates: int = 300
    deep_scan_limit: int = 60
    top_opportunities: int = 10
    min_score: float = 0.55
    weights: ScannerWeights = field(default_factory=ScannerWeights)


@dataclass
class AppConfig:
    bot: BotConfig = field(default_factory=BotConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)

    @property
    def can_place_orders(self) -> bool:
        return self.bot.live_trading_enabled and not self.bot.dry_run


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    load_dotenv()
    config_path = Path(path)
    data: dict = {}

    if config_path.exists():
        with config_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

    bot_data = data.get("bot", {})
    trading_data = data.get("trading", {})
    strategy_data = data.get("strategy", {})
    scanner_data = data.get("scanner", {})
    weights_data = scanner_data.get("weights", {})

    bot = BotConfig(
        poll_interval_seconds=int(bot_data.get("poll_interval_seconds", 300)),
        dry_run=_env_bool("BOT_DRY_RUN", bool(bot_data.get("dry_run", True))),
        live_trading_enabled=_env_bool(
            "BOT_LIVE_TRADING_ENABLED",
            bool(bot_data.get("live_trading_enabled", False)),
        ),
    )
    trading = TradingConfig(
        symbols=[str(s).upper() for s in trading_data.get("symbols", ["AAPL"])],
        trade_amount_usd=float(trading_data.get("trade_amount_usd", 50)),
        max_positions=int(trading_data.get("max_positions", 5)),
    )
    strategy = StrategyConfig(
        name=str(strategy_data.get("name", "sma_crossover")),
        params=dict(strategy_data.get("params", {})),
    )
    scanner = ScannerConfig(
        enabled=bool(scanner_data.get("enabled", True)),
        symbol_source=str(scanner_data.get("symbol_source", "scanner")),
        discovery_tags=[
            str(tag) for tag in scanner_data.get(
                "discovery_tags",
                ["100-most-popular", "10-most-popular", "top-movers"],
            )
        ],
        include_movers=bool(scanner_data.get("include_movers", True)),
        include_watchlists=bool(scanner_data.get("include_watchlists", True)),
        min_price_usd=float(scanner_data.get("min_price_usd", 5)),
        min_avg_volume=float(scanner_data.get("min_avg_volume", 100_000)),
        min_market_cap_usd=float(scanner_data.get("min_market_cap_usd", 500_000_000)),
        max_candidates=int(scanner_data.get("max_candidates", 300)),
        deep_scan_limit=int(scanner_data.get("deep_scan_limit", 60)),
        top_opportunities=int(scanner_data.get("top_opportunities", 10)),
        min_score=float(scanner_data.get("min_score", 0.55)),
        weights=ScannerWeights(
            momentum=float(weights_data.get("momentum", 0.25)),
            volume=float(weights_data.get("volume", 0.2)),
            range_position=float(weights_data.get("range_position", 0.15)),
            value=float(weights_data.get("value", 0.1)),
            analyst=float(weights_data.get("analyst", 0.2)),
        ),
    )

    return AppConfig(bot=bot, trading=trading, strategy=strategy, scanner=scanner)
