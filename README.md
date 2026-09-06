# Bizznizplan

NQ Pine-style backtester: paste a strategy, run it on a year of E-mini Nasdaq-100 (`NQ=F`), and see trades on the chart.

## Run

```bash
python3 scripts/fetch_nq.py    # refresh Yahoo NQ history
python3 server.py              # http://127.0.0.1:8765
```

Then open that URL. Pick 1D / 1H / 15m, NQ or MNQ, an example script (or your own), and click **Run script**.

## Data

| Interval | History | Source |
| --- | --- | --- |
| 1D | 365 days | Yahoo `NQ=F` continuous front month |
| 1H | 365 days | same |
| 15m | 60 days | Yahoo cap on 15-minute bars |

This is **not** a back-adjusted continuous contract. Rolls can gap. Intraday coverage follows Yahoo, including Globex hours. Orders fill at the **next bar open**, 1 tick of slippage, and a per-side commission ($2.25 NQ / $0.52 MNQ).

## Pine subset

Enough to backtest common NQ ideas:

- `strategy()`, `strategy.entry`, `strategy.close`, `strategy.exit` (`profit` / `loss` in ticks)
- `ta.sma`, `ta.ema`, `ta.rsi`, `ta.atr`, `ta.highest`, `ta.lowest`, `ta.crossover`, `ta.crossunder`
- `plot`, `input.int/float/bool`, `close[1]`, `and` / `or` / `not`

Not a full TradingView Pine runtime (no `request.security`, `varip`, libraries, or drawing objects).
