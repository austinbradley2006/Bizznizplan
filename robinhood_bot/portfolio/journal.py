from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass
class TradeRecord:
    timestamp: str
    symbol: str
    asset_type: str
    side: str
    quantity: float
    price: float
    notional: float
    reason: str
    dry_run: bool
    score: float | None = None


class TradeJournal:
    """Append-only trade log with simple daily P&L tracking."""

    def __init__(self, path: str = "data/trades.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, trade: TradeRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(trade)) + "\n")

    def load_records(self) -> list[dict]:
        if not self.path.exists():
            return []
        records: list[dict] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def daily_realized_pnl(self, day: date) -> float:
        records = self.load_records()
        day_str = day.isoformat()
        pnl = 0.0
        for record in records:
            if not record.get("timestamp", "").startswith(day_str):
                continue
            if record.get("dry_run"):
                continue
            notional = float(record.get("notional", 0))
            if record.get("side") == "sell":
                pnl += notional
            elif record.get("side") == "buy":
                pnl -= notional
        return pnl

    def recent_trades(self, limit: int = 20) -> list[dict]:
        return self.load_records()[-limit:]
