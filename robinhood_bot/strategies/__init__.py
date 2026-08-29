from robinhood_bot.strategies.base import Strategy
from robinhood_bot.strategies.sma_crossover import SMACrossoverStrategy

STRATEGIES: dict[str, type[Strategy]] = {
    "sma_crossover": SMACrossoverStrategy,
}


def build_strategy(name: str, params: dict) -> Strategy:
    strategy_cls = STRATEGIES.get(name)
    if strategy_cls is None:
        known = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"Unknown strategy '{name}'. Available: {known}")
    return strategy_cls(**params)
