# Robinhood Trading Bot

A configurable Python bot that connects to your Robinhood account and runs automated trading strategies.

> **Disclaimer:** This uses an **unofficial** Robinhood API via [pyhood](https://github.com/jamestford/pyhood). It is not affiliated with Robinhood Markets. Automated trading carries real financial risk — test thoroughly in dry-run mode before enabling live orders.

## Features

- Connect to Robinhood with persistent session (no password in code)
- **Market scanner** — discovers opportunities across Robinhood popular lists, movers, and your watchlists
- **Opportunity scoring** — ranks symbols by momentum, volume, valuation, analyst ratings, and strategy signals
- **Dry-run mode on by default** — logs signals without placing orders
- **Multi-market scanning** — stocks, options chains, and crypto pairs
- **Pluggable strategies** — SMA crossover, RSI, and breakout
- CLI: `status`, `scan`, `scan-options`, `scan-crypto`, `scan-all`, `once`, `run`
- Configurable symbols, trade size, and poll interval

## Quick start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Authenticate with Robinhood

```bash
pyhood setup login
```

Approve the device prompt in the Robinhood mobile app. Your session is saved to `~/.pyhood/session.json` and refreshes automatically.

### 3. Configure the bot

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` — start with defaults (`dry_run: true`, `live_trading_enabled: false`).

### 4. Check connection

```bash
python run_bot.py status
```

### 5. Scan for opportunities

```bash
python run_bot.py scan           # stocks
python run_bot.py scan-options   # option chains on active underlyings
python run_bot.py scan-crypto    # crypto pairs (requires pyhood setup crypto)
python run_bot.py scan-all       # all three markets
```

### 6. Run a test cycle (no real trades)

```bash
python run_bot.py once
```

### 7. Run continuously (still dry-run unless you opt in)

```bash
python run_bot.py run
```

## Enabling live trading

Only after you have tested dry-run behavior:

1. Set `dry_run: false` in `config.yaml`
2. Set `live_trading_enabled: true` in `config.yaml`

The bot will refuse to place real orders unless **both** flags are set correctly.

## Configuration

| Setting | Description |
| --- | --- |
| `bot.poll_interval_seconds` | Seconds between strategy evaluations |
| `bot.dry_run` | Log trades without executing |
| `bot.live_trading_enabled` | Safety gate for real orders |
| `trading.symbols` | Tickers to watch |
| `trading.trade_amount_usd` | Dollar amount per buy signal |
| `trading.max_positions` | Max simultaneous positions |
| `scanner.enabled` | Turn market scanning on/off |
| `scanner.symbol_source` | `scanner` (auto-discover) or `static` (manual list) |
| `scanner.discovery_tags` | Robinhood lists to scan (`100-most-popular`, `top-movers`, etc.) |
| `scanner.include_movers` | Include S&P 500 top movers |
| `scanner.include_watchlists` | Include your Robinhood watchlists |
| `scanner.min_score` | Minimum opportunity score (0–1) |
| `scanner.top_opportunities` | How many ranked setups to surface per scan |
| `strategy.name` | `sma_crossover`, `rsi`, or `breakout` |
| `options_scanner.*` | Option chain liquidity, delta, and OI filters |
| `crypto_scanner.*` | Crypto pair limits and momentum thresholds |

Environment overrides: `BOT_DRY_RUN`, `BOT_LIVE_TRADING_ENABLED`

For crypto scanning/trading, also run:

```bash
pyhood setup crypto
```

## How scanning works

1. **Discover** — Collect symbols from Robinhood tags, movers, and watchlists
2. **Screen** — Batch-fetch quotes and fundamentals; filter by price, volume, and market cap
3. **Score** — Rank by momentum, relative volume, 52-week range position, valuation, analyst ratings, and your strategy
4. **Trade** — In `scanner` mode, the bot acts on the top buy/sell candidates (respecting `max_positions`)

The scanner does not brute-force all ~5,000 Robinhood stocks each cycle (that would be slow and rate-limited). It focuses on what Robinhood surfaces as popular and moving, then deep-evaluates the best candidates.

## Strategies

### `sma_crossover`

Buys when the fast SMA crosses above the slow SMA; sells on a cross below.

### `rsi`

Buys when RSI is oversold; sells when overbought.

```yaml
strategy:
  name: rsi
  params:
    period: 14
    oversold: 30
    overbought: 70
```

### `breakout`

Buys on breakout above the recent range high; sells on breakdown below the range low.

```yaml
strategy:
  name: breakout
  params:
    lookback_period: 20
    min_bars: 25
```

Add your own by implementing `Strategy` in `robinhood_bot/strategies/` and registering it in `robinhood_bot/strategies/__init__.py`.

## Project layout

```
robinhood_bot/
  bot.py              # CLI and main loop
  client.py           # Robinhood connection wrapper
  config.py           # YAML + env config loader
  scanner/
    market_scanner.py  # Stock discovery and scoring
    options_scanner.py # Option chain scanner
    crypto_scanner.py  # Crypto pair scanner
  strategies/
    base.py
    sma_crossover.py
    rsi.py
    breakout.py
config.example.yaml
run_bot.py
requirements.txt
```

## Important notes

- Robinhood may rate-limit or block repeated failed logins — use `pyhood setup login`, not hardcoded passwords.
- Pattern day trading rules and margin requirements still apply.
- Past strategy performance does not guarantee future results.
- For crypto, pyhood supports Robinhood's official Crypto API separately (`pyhood setup crypto`).

## License

MIT
