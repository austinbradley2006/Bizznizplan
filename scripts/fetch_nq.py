#!/usr/bin/env python3
"""Download NQ continuous futures OHLCV from Yahoo Finance."""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "web" / "data"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 NQBacktest/1.0"}

DATASETS = (
    {"key": "1d", "interval": "1d", "days": 365},
    {"key": "1h", "interval": "1h", "days": 365},
    {"key": "15m", "interval": "15m", "days": 60},
)


def fetch_chart(symbol: str, interval: str, days: int) -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = (
        f"period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval={interval}"
        f"&events=div,split"
        f"&includePrePost=false"
    )
    url = f"{YAHOO.format(symbol=symbol)}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode())
    result = (payload.get("chart") or {}).get("result")
    if not result:
        err = (payload.get("chart") or {}).get("error")
        raise RuntimeError(f"Yahoo returned no data for {symbol} {interval}: {err}")
    return result[0]


def bars_from_chart(chart: dict, interval: str) -> list[dict]:
    timestamps = chart.get("timestamp") or []
    quote = (chart.get("indicators") or {}).get("quote") or [{}]
    q = quote[0]
    opens, highs, lows, closes, volumes = (
        q.get("open") or [],
        q.get("high") or [],
        q.get("low") or [],
        q.get("close") or [],
        q.get("volume") or [],
    )
    daily = interval.endswith("d")
    bars: list[dict] = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = (
            _num(opens[i] if i < len(opens) else None),
            _num(highs[i] if i < len(highs) else None),
            _num(lows[i] if i < len(lows) else None),
            _num(closes[i] if i < len(closes) else None),
        )
        if o is None or h is None or l is None or c is None:
            continue
        bar = {
            "time": _bar_time(int(ts), daily),
            "epoch": int(ts),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": int(_num(volumes[i] if i < len(volumes) else None) or 0),
        }
        bars.append(bar)
    return bars


def _num(value):
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def _bar_time(ts: int, daily: bool):
    if daily:
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    return ts


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NQ=F"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = {"symbol": symbol, "fetchedAt": datetime.now(timezone.utc).isoformat(), "sets": {}}
    for spec in DATASETS:
        chart = fetch_chart(symbol, spec["interval"], spec["days"])
        bars = bars_from_chart(chart, spec["interval"])
        meta = chart.get("meta") or {}
        payload = {
            "symbol": meta.get("symbol") or symbol,
            "exchange": meta.get("exchangeName") or "CME",
            "instrument": meta.get("instrumentType") or "FUTURE",
            "interval": spec["key"],
            "daysRequested": spec["days"],
            "lastPrice": meta.get("regularMarketPrice"),
            "bars": bars,
        }
        path = OUT_DIR / f"nq_{spec['key']}.json"
        path.write_text(json.dumps(payload))
        index["sets"][spec["key"]] = {
            "file": path.name,
            "bars": len(bars),
            "from": bars[0]["time"] if bars else None,
            "to": bars[-1]["time"] if bars else None,
        }
        print(f"{spec['key']}: {len(bars)} bars -> {path}")
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
