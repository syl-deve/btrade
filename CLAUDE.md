# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BITRADE CORE is a Python-based cryptocurrency auto-trading bot with a web dashboard. It runs RSI-based scalping strategies on Korean exchanges (Upbit/Bithumb) targeting Bitcoin (KRW-BTC). The UI is Korean-localized with optional English toggle.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure (copy and fill in API keys)
cp .env.template .env

# Run
python main.py  # Starts FastAPI server at http://localhost:8000

# Manual API test
python test_bithumb_auth.py
```

There is no automated test suite. No build step required.

## Architecture

### Data Flow

1. FastAPI app starts → SQLite DB initialized → exchange client authenticated
2. Background `trading_loop()` runs asynchronously on a configurable interval
3. Fetch OHLCV candles → calculate 14-period RSI → trigger buy/sell signals
4. Execute orders via exchange client → log to DB → send Discord webhook alert

### Key Files

- **`main.py`**: FastAPI app, session auth, all web routes, background trading task
- **`core/strategy.py`**: RSI calculation and buy/sell decision logic
- **`core/upbit_client.py`**: Thin wrapper around `pyupbit` library
- **`core/bithumb_client.py`**: Custom Bithumb V1 API client with JWT + SHA512 signing (pyupbit doesn't support Bithumb V1)
- **`core/discord_notifier.py`**: Webhook alerts on trade events
- **`models.py`**: SQLAlchemy ORM — `TradeHistory` and `BotSettings` (singleton row)
- **`config.py`**: Loads `.env`, sets SQLite path
- **`templates/index.html`**: Jinja2 template — Tailwind CSS + Chart.js dashboard

### Multi-Exchange Abstraction

Exchange is selected by the `EXCHANGE` env var (`UPBIT` or `BITHUMB`). A `get_client()` factory in `main.py` returns the appropriate client. Both clients expose the same interface (get_balance, get_current_price, buy_market_order, sell_market_order).

### Database

SQLite at `trading_bot.db`. Two tables:
- `TradeHistory`: One row per trade (symbol, side, price, volume, net_profit, timestamp)
- `BotSettings`: Single-row config persisted across restarts (RSI threshold, profit/stop-loss rates, trailing stop offset, avg buy price)

On startup, `main.py` auto-migrates missing columns for backward compatibility with existing DBs.

### Trading Logic Details

- **Fee-aware buy sizing**: Buys at 99.5% of KRW balance to absorb exchange fees
- **Trailing stop**: Tracks `highest_profit_rate` since entry; sells when current profit drops `trailing_stop_offset` below peak (default 0.2%)
- **Bithumb auth**: Requires SHA512 query hashing + JWT signing per request (see `bithumb_client.py`)

### API Endpoints

All routes require session cookie set by `POST /login`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Balances, RSI, price, trade history, bot settings |
| POST | `/api/settings` | Update RSI threshold, profit rate, stop-loss, etc. |
| POST | `/api/toggle` | Start/stop trading loop |
