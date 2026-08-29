from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TradeOpportunity:
    symbol: str
    score: float
    signal: str
    reason: str
    price: float
    change_pct: float = 0.0
    asset_type: str = "stock"
    sources: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    contract: dict[str, object] | None = None

    @property
    def display_symbol(self) -> str:
        if self.asset_type != "option" or not self.contract:
            return self.symbol
        option_type = str(self.contract.get("option_type", "")).upper()[:1]
        strike = self.contract.get("strike")
        expiration = self.contract.get("expiration")
        return f"{self.symbol} {strike}{option_type} {expiration}"


@dataclass
class ScanResult:
    market: str
    scanned_symbols: int
    evaluated_symbols: int
    opportunities: list[TradeOpportunity]
    buy_candidates: list[TradeOpportunity]
    sell_candidates: list[TradeOpportunity]
