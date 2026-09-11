# Daybook

A personal trading log inspired by modern trader journals — sessions, emotions, and P&L in one place.

## Features

- **Session calendar** with daily P&L coloring
- **Quick trade logging** (symbol, side, entry/exit, size, P&L, setup, notes)
- **Emotion tags** so psychology sits next to performance
- **Monthly stats** — net P&L, win rate, profit factor, expectancy
- **Evening reflections** with a simple mood score
- **Connect & import** — TradingView Strategy Tester CSV, webhook JSON, and broker CSVs (Robinhood, IBKR, Tradovate, thinkorswim, generic)
- **Local-first** — data stays in your browser (`localStorage`)

## Run

```bash
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

## Connect TradingView & brokers

Click **Connect** in the app header.

| Source | How |
| --- | --- |
| **TradingView** | Strategy Tester → List of Trades → Download CSV, or paste alert webhook JSON |
| **Robinhood / IBKR / Tradovate / thinkorswim** | Export trade history CSV from the broker, then upload |
| **Any broker** | CSV with Date, Symbol, Side, and P&L (entry/exit/size optional) |

Sample files live in `public/samples/`. Re-imports skip duplicates.

Live OAuth / always-on broker sync is not built yet — export → import is the supported path so stats stay accurate without sending credentials off-device.

## Notes

Demo trades load on first visit. Use **Reset demo** to restore the sample book.
