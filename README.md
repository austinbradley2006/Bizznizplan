# Robinhood Trading Bot

A configurable Python bot that connects to your Robinhood account and runs automated trading strategies.

> **Disclaimer:** This uses an **unofficial** Robinhood API via [pyhood](https://github.com/jamestford/pyhood). It is not affiliated with Robinhood Markets. Automated trading carries real financial risk — test thoroughly in dry-run mode before enabling live orders.

## Features

- Connect to Robinhood with persistent session (no password in code)
- **Dry-run mode on by default** — logs signals without placing orders
- Pluggable strategies (includes SMA crossover example)
- CLI: `status`, `once` (single cycle), `run` (continuous loop)
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

### 5. Run a test cycle (no real trades)

```bash
python run_bot.py once
```

### 6. Run continuously (still dry-run unless you opt in)

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
| `strategy.name` | Strategy to use (`sma_crossover`) |
| `strategy.params` | Strategy-specific parameters |

Environment overrides: `BOT_DRY_RUN`, `BOT_LIVE_TRADING_ENABLED`

## Strategies

### `sma_crossover` (default)

Buys when the fast simple moving average crosses above the slow SMA; sells on a cross below.

```yaml
strategy:
  name: sma_crossover
  params:
    fast_period: 10
    slow_period: 30
    min_bars: 35
```

Add your own by implementing `Strategy` in `robinhood_bot/strategies/` and registering it in `robinhood_bot/strategies/__init__.py`.

## Project layout

```
robinhood_bot/
  bot.py              # CLI and main loop
  client.py           # Robinhood connection wrapper
  config.py           # YAML + env config loader
  strategies/
    base.py           # Strategy interface
    sma_crossover.py  # Example strategy
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
