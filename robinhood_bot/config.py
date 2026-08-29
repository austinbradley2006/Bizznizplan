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
class AppConfig:
    bot: BotConfig = field(default_factory=BotConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)

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

    return AppConfig(bot=bot, trading=trading, strategy=strategy)
