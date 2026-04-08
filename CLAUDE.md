# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BITRADE CORE is a Python-based cryptocurrency auto-trading bot with a web dashboard. It runs a configurable filter entry strategy (RSI + Bollinger Band, with optional MACD + Volume toggles) with ATR-based dynamic stop-loss, trailing profit-taking, and risk management on Bithumb (Upbit currently disabled) targeting Bitcoin (KRW-BTC). The UI is Korean-localized with optional English toggle, Bauhaus design system.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure
cp .env.template .env

# Run
python main.py  # Starts FastAPI server at http://localhost:8000

# Manual API test
python test_bithumb_auth.py
```

There is no automated test suite. No build step required.

## Architecture

### Data Flow

1. FastAPI app starts → `_run_db_migrations()` 즉시 실행 (모듈 로드 시) → SQLite DB 컬럼 자동 추가 + fee 소급 적용
2. Background `trading_loop()` runs every 60 seconds
3. Fetch OHLCV → RSI + Bollinger(+optional MACD/Volume) + ATR 계산 → 매수/매도 판단
4. Execute orders → log to DB (수수료 포함) → Discord webhook alert

### Key Files

- **`main.py`**: FastAPI app, session auth, all API routes, background trading loop, helper functions
  - `_run_db_migrations()`: 모듈 로드 시 즉시 실행, trade_history.fee 소급 적용
  - `_reset_position()`: avg_buy_price, highest_profit_rate, buy_count, position_opened_at 초기화
  - `_record_sell()`: 매도 기록, 수수료 계산 포함, `_reset_position` 호출
  - `_record_buy()`: 매수 기록, 수수료 계산 포함
  - `_check_daily_loss()`: 일일 손실 초과 시 봇 정지
  - `_check_consecutive_loss()`: 연속 손절 시 쿨다운 설정
  - `get_fee_rate()`: 거래소별 수수료율 반환 (업비트 0.05%, 빗썸 0.04% 쿠폰)
- **`core/strategy.py`**: 모든 지표 계산
  - `get_rsi()`: 14기간 RSI, div-by-zero 방지 처리
  - `get_bollinger()`: 20기간 2σ, (upper, middle, lower) 반환
  - `is_below_bollinger_lower()`: 현재가 ≤ 하단밴드
  - `get_macd()`: 12/26/9, 최근 3봉 히스토그램 반환
  - `is_macd_reversing()`: hist[-1] < 0 AND hist[-1] > hist[-2]
  - `is_volume_surging()`: 현재 거래량 ≥ 20봉 평균 × multiplier
  - `get_volume_ratio()`: (current, avg, ratio) 반환
  - `get_atr()`: 14기간 ATR
  - `get_dynamic_stop_loss()`: ATR 기반 손절율 (-0.5 ~ -3.0%)
- **`core/bithumb_client.py`**: Bithumb V1 JWT + SHA512 커스텀 클라이언트
- **`core/upbit_client.py`**: pyupbit 래퍼 (현재 UI에서 비활성화)
- **`core/discord_notifier.py`**: 웹훅 알림
- **`models.py`**: SQLAlchemy ORM — `TradeHistory`, `BotSettings`
- **`config.py`**: `.env` 로드
- **`templates/index.html`**: Jinja2 + Tailwind CSS + Chart.js 대시보드
- **`static/css/bauhaus.css`**: Bauhaus 디자인 시스템

### Multi-Exchange Abstraction

`EXCHANGE` env var (`BITHUMB` 권장, `UPBIT` UI에서 비활성화). `get_client()` 팩토리가 동일 인터페이스 반환 (`get_krw_balance`, `get_coin_balance`, `get_current_price`, `buy_market_order`, `sell_market_order`).

### Database

SQLite at `trading_bot.db`. 시작 시 `_run_db_migrations()`이 raw sqlite3로 누락 컬럼 자동 추가 및 fee 전체 재계산.

**TradeHistory 컬럼:**

| 컬럼 | 설명 |
|---|---|
| `symbol` | 거래 심볼 (KRW-BTC) |
| `side` | BUY / SELL |
| `price` | 체결가 |
| `volume` | 수량 |
| `total_amount` | 거래금액 (원화) |
| `fee` | 수수료 (원화, 거래소별 요율 적용) |
| `net_profit` | 순익 (수수료 차감 후, SELL만 유효) |
| `timestamp` | 체결 시각 |

**BotSettings 컬럼:**

| 컬럼 | 기본값 | 설명 |
|---|---|---|
| `rsi_threshold` | 35.0 | 1차 매수 RSI 기준 |
| `rsi_threshold_2` | 28.0 | 2차 매수 RSI 기준 |
| `target_profit_rate` | 1.5 | 트레일링 익절 목표 (%) |
| `stop_loss_rate` | -1.0 | 손절 기준 (%, ATR 계산 불가 시 폴백) |
| `trailing_stop_offset` | 0.3 | 고점 대비 하락 익절 간격 (%) |
| `first_buy_ratio` | 0.6 | 1차 매수 비율 (잔고의 60%) |
| `buy_count` | 0 | 현재 포지션 분할매수 횟수 (0/1/2) |
| `avg_buy_price` | 0.0 | 현재 포지션 평단가 |
| `highest_profit_rate` | 0.0 | 진입 후 최고 수익률 (트레일링용) |
| `position_opened_at` | null | 포지션 진입 시각 (UTC) |
| `exchange` | BITHUMB | 활성 거래소 |
| `use_bollinger` | True | 볼린저밴드 하단 필터 |
| `use_macd` | True | MACD 히스토그램 반전 필터 |
| `use_volume_filter` | True | 거래량 급증 필터 |
| `volume_multiplier` | 1.5 | 거래량 기준 배수 (20봉 평균 대비) |
| `atr_multiplier` | 1.5 | ATR 기반 손절폭 배수 |
| `max_hold_hours` | 4.0 | 최대 보유 시간 (DB 컬럼 존재하나 강제 청산 비활성화됨) |
| `daily_loss_limit` | -50000 | 일일 최대 손실 한도 (원, 초과 시 봇 정지) |
| `max_consecutive_loss` | 3 | 연속 손절 허용 횟수 |
| `cooldown_minutes` | 60 | 연속 손절 후 매수 금지 시간 (분) |
| `cooldown_until` | null | 쿨다운 종료 시각 (로컬 시간) |

### Fee Rates

| 거래소 | 요율 | 비고 |
|---|---|---|
| 빗썸 | 0.04% | 수수료 쿠폰 적용 (30일 갱신 필요) |
| 업비트 | 0.05% | UI 비활성화 상태 |

수수료는 매수+매도 양쪽 합산하여 `net_profit`에 반영. 앱 재시작 시 전체 거래 fee 재계산.

### Trading Logic

**1차 매수** (미보유 상태):
1. RSI ≤ `rsi_threshold` (필수)
2. 볼린저밴드 하단 이탈 (`use_bollinger` 토글)
3. MACD 히스토그램 음수 구간 반전 (`use_macd` 토글)
4. 거래량 ≥ 20봉 평균 × `volume_multiplier` (`use_volume_filter` 토글)
- 활성화된 필터 모두 통과 시 잔고 × `first_buy_ratio` × 0.995 매수
- `position_opened_at` = UTC now, `buy_count = 1`

**2차 추가매수** (1차 보유 중):
- RSI ≤ `rsi_threshold_2` AND 현재가 < `avg_buy_price`
- 잔고 전량 × 0.995 추가매수
- 평단 = (1차 실제 투자금 + 2차 금액) / 총 수량 (DB 기반 정확 계산)
- `buy_count = 2`

**매도 우선순위** (보유 중):
1. ATR 동적 손절 — `get_dynamic_stop_loss()` 계산값 (범위: -0.5 ~ -3.0%), 계산 실패 시 `stop_loss_rate` 폴백
   - 손절 후 `_check_consecutive_loss()` 호출
2. ~~보유시간 초과 청산~~ — 비활성화
3. 트레일링 익절 — `highest_profit_rate` ≥ `target_profit_rate` 후 `trailing_stop_offset` 하락 시

**리스크 관리** (매수 전 체크):
- 일일 손실 한도: 당일 실현 손실 합계 ≤ `daily_loss_limit` → `is_running = False` 자동 정지
- 연속 손절 쿨다운: 최근 `max_consecutive_loss`회 매도 전부 손실 → `cooldown_until` 시각까지 매수 금지

**즉시매도** (`POST /api/sell_now`): 수동 전량 시장가 매도, 봇 상태 유지

### Dashboard UI

- **잔고 섹션**: KRW 잔고, 코인 수량 + 한화 평가액, 거래 단계 상태 문구
- **실시간 수익률 카드**: 현재 수익률, 평가손익, 분할매수 뱃지
- **스탯 카드 (7개)**: RSI, 매매당 평균손익, 오늘 손익, 마지막 거래, MACD, 거래량, 볼린저밴드
- **누적수익 차트**: 다크 배경 Chart.js
- **거래 내역 테이블**: 시간, 구분, 체결가, 수량, 거래금액, 수수료, 손익

### API Endpoints

All routes require session cookie set by `POST /login`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/status` | 잔고, RSI, 볼린저/MACD/거래량, 가격, 거래내역, 설정, 통계 전체 |
| POST | `/api/settings` | 전체 거래 설정 업데이트 |
| POST | `/api/toggle` | 봇 시작/정지 |
| POST | `/api/sell_now` | 즉시 전량 매도 |

### Dashboard Stats (`/api/status` 반환)

| 필드 | 설명 |
|---|---|
| `avg_profit_per_trade` | 전체 순익 ÷ 매도 횟수 |
| `today_net_profit` | 당일 실현 손익 |
| `last_trade_elapsed_minutes` | 마지막 거래 경과 시간 (분) |
| `buy_count` | 현재 분할매수 횟수 |
| `bollinger` | upper/middle/lower/is_below |
| `macd` | histogram/histogram_prev/is_reversing |
| `volume` | current/avg/ratio/is_surging |
