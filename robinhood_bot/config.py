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
    sizing_mode: str = "fixed"  # fixed | percent_portfolio | volatility
    portfolio_pct_per_trade: float = 0.05
    max_position_pct_of_buying_power: float = 0.15
    risk_pct_per_trade: float = 0.01
    atr_period: int = 14
    atr_multiplier: float = 2.0


@dataclass
class RiskConfig:
    max_daily_loss_usd: float = 250.0
    stop_loss_pct: float = 8.0
    take_profit_pct: float = 15.0
    min_opportunity_score: float = 0.5
    trade_only_during_market_hours: bool = True
    journal_path: str = "data/trades.jsonl"


@dataclass
class StrategyConfig:
    name: str = "composite"
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
class TelegramConfig:
    enabled: bool = True
    bot_token: str = ""
    allowed_chat_ids: list[int] = field(default_factory=list)


@dataclass
class TwilioConfig:
    enabled: bool = False
    account_sid: str = ""
    auth_token: str = ""
    phone_number: str = ""
    allowed_numbers: list[str] = field(default_factory=list)
    webhook_port: int = 8080
    verify_signatures: bool = True


@dataclass
class MessagingConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    twilio: TwilioConfig = field(default_factory=TwilioConfig)


@dataclass
class AppConfig:
    bot: BotConfig = field(default_factory=BotConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    options_scanner: OptionsScannerConfig = field(default_factory=OptionsScannerConfig)
    crypto_scanner: CryptoScannerConfig = field(default_factory=CryptoScannerConfig)
    messaging: MessagingConfig = field(default_factory=MessagingConfig)

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
    risk_data = data.get("risk", {})
    strategy_data = data.get("strategy", {})
    scanner_data = data.get("scanner", {})
    options_data = data.get("options_scanner", {})
    crypto_data = data.get("crypto_scanner", {})
    messaging_data = data.get("messaging", {})
    telegram_data = messaging_data.get("telegram", {})
    twilio_data = messaging_data.get("twilio", {})
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
        sizing_mode=str(trading_data.get("sizing_mode", "fixed")),
        portfolio_pct_per_trade=float(trading_data.get("portfolio_pct_per_trade", 0.05)),
        max_position_pct_of_buying_power=float(
            trading_data.get("max_position_pct_of_buying_power", 0.15)
        ),
        risk_pct_per_trade=float(trading_data.get("risk_pct_per_trade", 0.01)),
        atr_period=int(trading_data.get("atr_period", 14)),
        atr_multiplier=float(trading_data.get("atr_multiplier", 2.0)),
    )
    risk = RiskConfig(
        max_daily_loss_usd=float(risk_data.get("max_daily_loss_usd", 250)),
        stop_loss_pct=float(risk_data.get("stop_loss_pct", 8)),
        take_profit_pct=float(risk_data.get("take_profit_pct", 15)),
        min_opportunity_score=float(risk_data.get("min_opportunity_score", 0.5)),
        trade_only_during_market_hours=bool(
            risk_data.get("trade_only_during_market_hours", True)
        ),
        journal_path=str(risk_data.get("journal_path", "data/trades.jsonl")),
    )
    strategy = StrategyConfig(
        name=str(strategy_data.get("name", "composite")),
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

    messaging = MessagingConfig(
        telegram=TelegramConfig(
            enabled=bool(telegram_data.get("enabled", True)),
            bot_token=str(telegram_data.get("bot_token", "")),
            allowed_chat_ids=[int(x) for x in telegram_data.get("allowed_chat_ids", [])],
        ),
        twilio=TwilioConfig(
            enabled=bool(twilio_data.get("enabled", False)),
            account_sid=str(twilio_data.get("account_sid", "")),
            auth_token=str(twilio_data.get("auth_token", "")),
            phone_number=str(twilio_data.get("phone_number", "")),
            allowed_numbers=[str(n) for n in twilio_data.get("allowed_numbers", [])],
            webhook_port=int(twilio_data.get("webhook_port", 8080)),
            verify_signatures=bool(twilio_data.get("verify_signatures", True)),
        ),
    )

    return AppConfig(
        bot=bot,
        trading=trading,
        risk=risk,
        strategy=strategy,
        scanner=scanner,
        options_scanner=options_scanner,
        crypto_scanner=crypto_scanner,
        messaging=messaging,
    )
