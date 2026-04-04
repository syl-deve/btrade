# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BITRADE CORE is a Python-based cryptocurrency auto-trading bot with a web dashboard. It runs RSI + Bollinger Band based split-entry strategies on Korean exchanges (Upbit/Bithumb) targeting Bitcoin (KRW-BTC). The UI is Korean-localized with optional English toggle.

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

1. FastAPI app starts → SQLite DB auto-migrated → exchange client authenticated
2. Background `trading_loop()` runs asynchronously every 60 seconds
3. Fetch OHLCV candles → calculate RSI + Bollinger Band → trigger buy/sell signals
4. Execute orders via exchange client → log to DB → send Discord webhook alert

### Key Files

- **`main.py`**: FastAPI app, session auth, all web routes, background trading task, `_reset_position()` / `_record_sell()` / `_record_buy()` helpers
- **`core/strategy.py`**: RSI + Bollinger Band calculation (`get_rsi`, `get_bollinger`, `is_below_bollinger_lower`)
- **`core/upbit_client.py`**: Thin wrapper around `pyupbit` library
- **`core/bithumb_client.py`**: Custom Bithumb V1 API client with JWT + SHA512 signing
- **`core/discord_notifier.py`**: Webhook alerts on trade events
- **`models.py`**: SQLAlchemy ORM — `TradeHistory` and `BotSettings` (singleton row)
- **`config.py`**: Loads `.env`, sets SQLite path
- **`templates/index.html`**: Jinja2 template — Tailwind CSS + Chart.js dashboard
- **`static/css/bauhaus.css`**: Bauhaus design system (geometric shapes, hard shadows, grid)

### Multi-Exchange Abstraction

Exchange is selected by the `EXCHANGE` env var (`UPBIT` or `BITHUMB`). A `get_client()` factory in `main.py` returns the appropriate client. Both clients expose the same interface (`get_krw_balance`, `get_coin_balance`, `get_current_price`, `buy_market_order`, `sell_market_order`).

### Database

SQLite at `trading_bot.db`. Two tables:
- `TradeHistory`: One row per trade (symbol, side, price, volume, net_profit, timestamp)
- `BotSettings`: Single-row config persisted across restarts

`BotSettings` columns:
| Column | Default | Description |
|---|---|---|
| `rsi_threshold` | 35.0 | 1차 매수 RSI 기준 |
| `rsi_threshold_2` | 28.0 | 2차 매수 RSI 기준 |
| `target_profit_rate` | 1.5 | 트레일링 익절 목표 (%) |
| `stop_loss_rate` | -1.0 | 손절 기준 (%) |
| `trailing_stop_offset` | 0.3 | 고점 대비 하락 익절 간격 (%) |
| `buy_count` | 0 | 현재 포지션 분할매수 횟수 |
| `use_bollinger` | True | 볼린저밴드 하단 필터 on/off |
| `first_buy_ratio` | 0.6 | 1차 매수 비율 (잔고의 60%) |
| `avg_buy_price` | 0.0 | 현재 포지션 평단가 |
| `highest_profit_rate` | 0.0 | 진입 후 최고 수익률 (트레일링용) |
| `exchange` | UPBIT | 활성 거래소 |

On startup, `main.py` auto-migrates missing columns for backward compatibility with existing DBs.

### Trading Logic

**1차 매수** (미보유 상태):
- RSI ≤ `rsi_threshold` AND 볼린저밴드 하단 이탈 (`use_bollinger=True` 시)
- 잔고 × `first_buy_ratio` × 0.995 금액 시장가 매수
- `buy_count = 1` 설정

**2차 추가매수** (1차 보유 중):
- RSI ≤ `rsi_threshold_2` AND 현재가 < `avg_buy_price`
- 잔고 전량 × 0.995 추가 매수, 평단 재계산
- `buy_count = 2` 설정

**트레일링 익절**:
- `highest_profit_rate` ≥ `target_profit_rate` 도달 후
- 현재 수익률 ≤ `highest_profit_rate` - `trailing_stop_offset` 시 전량 매도

**긴급 손절**: 수익률 ≤ `stop_loss_rate` → 즉시 전량 매도

**즉시매도**: `POST /api/sell_now` → 수동 전량 매도 (봇 상태 유지)

### API Endpoints

All routes require session cookie set by `POST /login`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Balances, RSI, price, trade history, bot settings, stats |
| POST | `/api/settings` | Update all trading config parameters |
| POST | `/api/toggle` | Start/stop trading loop |
| POST | `/api/sell_now` | Instant full sell at market price |

### Dashboard Stats

`/api/status` returns computed stats:
- `avg_profit_per_trade`: 전체 순익 ÷ 매도 횟수
- `today_net_profit`: 당일 실현 손익
- `last_trade_elapsed_minutes`: 마지막 거래 경과 시간 (분)
- `buy_count`: 현재 분할매수 횟수
