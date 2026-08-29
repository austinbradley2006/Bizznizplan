# Robinhood Trading Bot

A production-oriented Python bot that connects to Robinhood, scans stocks/options/crypto for opportunities, manages risk, and executes trades with full audit logging.

> **Disclaimer:** Uses an **unofficial** Robinhood API via [pyhood](https://github.com/jamestford/pyhood). Not affiliated with Robinhood Markets. Automated trading carries real financial risk — test thoroughly in dry-run mode before enabling live orders.

## Highlights

- **Composite strategy** — votes across RSI, SMA crossover, breakout, MACD, Bollinger Bands, and trend
- **Multi-market scanning** — stocks, options chains, and crypto pairs
- **Risk management** — stop-loss, take-profit, daily loss limits, market-hours guard, position sizing (fixed / % portfolio / ATR volatility)
- **Execution engine** — unified stock + crypto execution with pre-trade checks
- **Trade journal** — append-only log of every action (`data/trades.jsonl`)
- **Backtesting** — quick historical strategy evaluation
- **Dry-run by default** — no real orders unless explicitly enabled

## Quick start

```bash
pip install -r requirements.txt
pyhood setup login
cp config.example.yaml config.yaml
python run_bot.py status
python run_bot.py scan-all
python run_bot.py backtest AAPL MSFT NVDA
python run_bot.py once      # dry-run cycle
```

For crypto: `pyhood setup crypto`

## Text your bot

The easiest way is **Telegram** (works like texting from your phone):

1. Open Telegram and message **@BotFather**
2. Send `/newbot`, follow prompts, copy the token
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
4. Start the bot listener:
   ```bash
   python run_bot.py telegram
   ```
5. Find your bot in Telegram, send `/start` — it replies with your chat ID
6. Text commands: `STATUS`, `SCAN`, `SCAN ALL`, `ONCE`, `JOURNAL`, `HELP`

Test locally without Telegram:
```bash
python run_bot.py reply "status"
```

### Real SMS (Twilio)

For actual text messages via phone number:

1. Create a [Twilio](https://www.twilio.com) account and buy a number
2. Set in `.env`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
3. In `config.yaml`, enable `messaging.twilio` and add your phone to `allowed_numbers`
4. Expose the server (e.g. `ngrok http 8080`) and set Twilio webhook to `https://YOUR_URL/sms`
5. Run: `python run_bot.py text`

## Commands

| Command | Description |
| --- | --- |
| `status` | Account, positions, P&L, risk settings, recent trades |
| `journal` | Full trade log |
| `scan` | Stock opportunities |
| `scan-options` | Option chain opportunities |
| `scan-crypto` | Crypto pair opportunities |
| `scan-all` | All markets |
| `backtest SYMBOL...` | Historical strategy test |
| `once` | Single trading cycle |
| `run` | Continuous loop |
| `telegram` | Listen for Telegram messages |
| `text` | SMS webhook server (Twilio) |
| `reply "..."` | Test a command locally |

## Architecture

```
robinhood_bot/
  bot.py                 # CLI + orchestration
  client.py              # Robinhood / crypto API wrapper
  config.py              # YAML configuration
  execution/engine.py    # Trade execution + journaling
  risk/
    manager.py           # Pre-trade risk checks, stop-loss rules
    position_sizer.py    # Fixed / % / ATR-based sizing
  portfolio/journal.py   # Trade audit log
  scanner/               # Stock, options, crypto scanners
  strategies/
    composite.py         # Recommended multi-signal strategy
    rsi.py, breakout.py, sma_crossover.py
    indicators.py        # RSI, SMA, EMA, MACD, ATR, Bollinger
  backtest/runner.py     # Simple walk-forward backtest
```

## Recommended configuration

The example config uses:
- `strategy.name: composite` — best out-of-the-box signal quality
- `scanner.symbol_source: scanner` — auto-discover across Robinhood
- `trading.sizing_mode: volatility` — ATR-based position sizing
- `risk.stop_loss_pct: 8` / `take_profit_pct: 15` — automatic exits
- `bot.dry_run: true` — safe default

## Enabling live trading

Only after backtesting and dry-run validation:

1. `dry_run: false`
2. `live_trading_enabled: true`

Both are required. The bot will not place real orders otherwise.

## Risk controls

| Setting | Purpose |
| --- | --- |
| `risk.max_daily_loss_usd` | Halt trading after daily realized loss |
| `risk.stop_loss_pct` | Auto-sell losing positions |
| `risk.take_profit_pct` | Auto-sell winning positions |
| `risk.min_opportunity_score` | Minimum scanner score to trade |
| `risk.trade_only_during_market_hours` | Block stock trades when market closed |
| `trading.max_positions` | Cap simultaneous holdings |
| `trading.sizing_mode` | `fixed`, `percent_portfolio`, or `volatility` |

## Strategies

| Name | Description |
| --- | --- |
| `composite` | **Recommended.** Weighted vote across all signals |
| `rsi` | Oversold/overbought |
| `breakout` | Range breakout/breakdown |
| `sma_crossover` | Moving average crossover |

## Testing

```bash
pytest tests/ -q
```

## Important notes

- Robinhood may rate-limit logins — use `pyhood setup login`, never hardcode passwords
- Pattern day trading rules and margin requirements still apply
- Scanner focuses on Robinhood discovery surfaces (popular, movers, watchlists), not all ~5,000 tickers
- Past performance does not guarantee future results

## License

MIT
