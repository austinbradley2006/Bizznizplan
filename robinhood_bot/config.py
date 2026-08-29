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
class OptionsScannerConfig:
    enabled: bool = True
    underlying_symbols: list[str] = field(default_factory=list)
    max_underlyings: int = 15
    min_option_volume: int = 100
    min_open_interest: int = 500
    target_delta_min: float = 0.25
    target_delta_max: float = 0.55
    min_score: float = 0.45
    top_opportunities: int = 10


@dataclass
class CryptoScannerConfig:
    enabled: bool = True
    pairs: list[str] = field(default_factory=list)
    max_pairs: int = 20
    min_bars: int = 20
    interval: str = "hour"
    span: str = "week"
    rsi_period: int = 14
    fast_period: int = 10
    slow_period: int = 30
    oversold: float = 30.0
    overbought: float = 70.0
    min_score: float = 0.5
    top_opportunities: int = 10


@dataclass
class AppConfig:
    bot: BotConfig = field(default_factory=BotConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    options_scanner: OptionsScannerConfig = field(default_factory=OptionsScannerConfig)
    crypto_scanner: CryptoScannerConfig = field(default_factory=CryptoScannerConfig)

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
    options_data = data.get("options_scanner", {})
    crypto_data = data.get("crypto_scanner", {})
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

    options_scanner = OptionsScannerConfig(
        enabled=bool(options_data.get("enabled", True)),
        underlying_symbols=[str(s).upper() for s in options_data.get("underlying_symbols", [])],
        max_underlyings=int(options_data.get("max_underlyings", 15)),
        min_option_volume=int(options_data.get("min_option_volume", 100)),
        min_open_interest=int(options_data.get("min_open_interest", 500)),
        target_delta_min=float(options_data.get("target_delta_min", 0.25)),
        target_delta_max=float(options_data.get("target_delta_max", 0.55)),
        min_score=float(options_data.get("min_score", 0.45)),
        top_opportunities=int(options_data.get("top_opportunities", 10)),
    )
    crypto_scanner = CryptoScannerConfig(
        enabled=bool(crypto_data.get("enabled", True)),
        pairs=[str(p).upper() for p in crypto_data.get("pairs", [])],
        max_pairs=int(crypto_data.get("max_pairs", 20)),
        min_bars=int(crypto_data.get("min_bars", 20)),
        interval=str(crypto_data.get("interval", "hour")),
        span=str(crypto_data.get("span", "week")),
        rsi_period=int(crypto_data.get("rsi_period", 14)),
        fast_period=int(crypto_data.get("fast_period", 10)),
        slow_period=int(crypto_data.get("slow_period", 30)),
        oversold=float(crypto_data.get("oversold", 30)),
        overbought=float(crypto_data.get("overbought", 70)),
        min_score=float(crypto_data.get("min_score", 0.5)),
        top_opportunities=int(crypto_data.get("top_opportunities", 10)),
    )

    return AppConfig(
        bot=bot,
        trading=trading,
        strategy=strategy,
        scanner=scanner,
        options_scanner=options_scanner,
        crypto_scanner=crypto_scanner,
    )
