# CLAUDE.md

AI 코딩 어시스턴트를 위한 구현 상세 가이드입니다. 프로젝트 개요·전략·설치는 README.md를 참조하세요.

## Commands

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py  # http://localhost:8000
```

No automated test suite. No build step.

## Architecture

### Data Flow

1. FastAPI 앱 시작 → `_run_db_migrations()` 즉시 실행 (모듈 로드 시) → SQLite 컬럼 자동 추가 + fee 소급 적용
2. Background `trading_loop()` 60초마다 실행
3. OHLCV 조회 → 지표 계산 → 매수/매도 판단 → DB 기록 → Discord 알림

### Key Files

- **`main.py`**: FastAPI 앱, 인증, API 라우트, 트레이딩 루프
  - `_run_db_migrations()`: 모듈 로드 시 즉시 실행. BUY fee = `total_amount × 0.0004`, SELL fee = `total_amount × 0.0004` (매도 단건 기준, 빗썸 앱 일치)
  - `_reset_position()`: avg_buy_price, highest_profit_rate, buy_count, position_opened_at 초기화
  - `_record_sell()`: 매도 기록. DB fee = 매도금액×0.04% (단건, 빗썸 앱 기준). net_profit = 매도금액 - 매수원금 - (매수+매도 수수료 합산). `_reset_position` 호출. `/api/sell_now`도 이 함수 재사용
  - `_record_buy()`: 매수 기록. fee = 매수금액×0.04%
  - `_check_daily_loss()`: 당일 net_profit 합계 ≤ daily_loss_limit → is_running = False
  - `_check_consecutive_loss()`: 최근 N매도 전부 손실 → cooldown_until 설정 (로컬 시간)
  - `get_fee_rate()`: BITHUMB=0.0004, UPBIT=0.0005
  - `SecurityHeadersMiddleware`: 모든 응답에 CSP, X-Frame-Options, HSTS 등 주입
  - `verify_csrf()`: POST/PUT/DELETE에 `X-CSRF-Token` 헤더 검증 (Depends로 주입)
  - `SettingsUpdate` (Pydantic): rsi_threshold(10~90), stop_loss_rate(-50~-0.1) 등 범위 검증
  - `LOGIN_ATTEMPTS`: IP별 로그인 실패 카운터. 5회 초과 시 600초 차단
- **`core/strategy.py`**: 모든 지표 계산
  - `get_rsi()`: 14기간, `ad.replace(0, 1e-10)` div-by-zero 방지, NaN → None 반환
  - `get_bollinger()`: 20기간 2σ → (upper, middle, lower)
  - `is_below_bollinger_lower()`: 현재가 ≤ lower
  - `get_macd()`: 12/26/9, 최근 3봉 히스토그램 반환
  - `is_macd_reversing()`: hist[-1] < 0 AND hist[-1] > hist[-2]
  - `is_volume_surging()`: current_vol ≥ 20봉평균 × multiplier
  - `get_atr()`: 14기간 ATR
  - `get_dynamic_stop_loss()`: ATR × atr_multiplier, 범위 클램프 -0.5% ~ -3.0%
  - `/api/status`: 지표(RSI/볼린저/MACD/거래량)·캔들 데이터는 `indicator_exchange = "BITHUMB"`으로 고정 조회 (public API, 인증 불필요). `strategy=None` 시 `ScalperStrategy()` fallback 생성. 현재가 실패 시 `bithumb_client.get_current_price()` fallback
  - `candle_data`: 빗썸 OHLCV DataFrame은 인덱스가 정수, 시각은 `candle_date_time_kst` 컬럼 → `strftime` 직접 호출 불가. `candle_date_time_kst` → `candle_date_time_utc` → `timestamp` 컬럼 순서로 탐색
- **`core/strategy.py`**: 모든 지표 계산
  - `get_ohlcv()`: BITHUMB이면 `BithumbClient.get_ohlcv()`, UPBIT이면 `pyupbit.get_ohlcv()`
- **`models.py`**: TradeHistory, BotSettings SQLAlchemy ORM
- **`config.py`**: .env 로드
- **`templates/index.html`**: Jinja2 + Tailwind + Chart.js. `csrf_token` context로 전달받아 API 헤더에 사용
- **`static/css/bauhaus.css`**: Bauhaus 디자인. `.hint-btn` (카드 절대위치), `.cfg-hint-btn` (모달 인라인)

### Database Schema

**TradeHistory:**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `symbol` | String | KRW-BTC |
| `side` | String | BUY / SELL |
| `price` | Float | 체결가 |
| `volume` | Float | 수량 |
| `total_amount` | Float | 거래금액 (원화) |
| `fee` | Float | BUY: 매수금액×0.04%, SELL: 매도금액×0.04% (단건, 빗썸 앱 기준) |
| `net_profit` | Float | 순익 (SELL만 유효) |
| `timestamp` | DateTime | 체결 시각 |

**BotSettings:**

| 컬럼 | 기본값 | 설명 |
|---|---|---|
| `rsi_threshold` | 35.0 | 1차 매수 RSI |
| `rsi_threshold_2` | 28.0 | 2차 매수 RSI |
| `target_profit_rate` | 1.5 | 트레일링 익절 목표 (%) |
| `stop_loss_rate` | -1.0 | ATR 실패 시 폴백 손절 (%) |
| `trailing_stop_offset` | 0.3 | 고점 대비 하락 익절 간격 (%) |
| `first_buy_ratio` | 0.6 | 1차 매수 비율 |
| `buy_count` | 0 | 현재 분할매수 횟수 (0/1/2) |
| `avg_buy_price` | 0.0 | 현재 포지션 평단가 |
| `highest_profit_rate` | 0.0 | 진입 후 최고 수익률 (트레일링용) |
| `position_opened_at` | null | 포지션 진입 시각 (UTC) |
| `exchange` | BITHUMB | 활성 거래소 |
| `use_bollinger` | True | 볼린저밴드 하단 필터 |
| `use_macd` | True | MACD 반전 필터 |
| `use_volume_filter` | True | 거래량 급증 필터 |
| `volume_multiplier` | 1.5 | 거래량 배수 (20봉 평균 대비) |
| `atr_multiplier` | 1.5 | ATR 손절폭 배수 |
| `max_hold_hours` | 4.0 | DB 컬럼 존재, 강제 청산 비활성화 |
| `daily_loss_limit` | -50000 | 일일 손실 한도 (원) |
| `max_consecutive_loss` | 3 | 연속 손절 허용 횟수 |
| `cooldown_minutes` | 60 | 쿨다운 시간 (분) |
| `cooldown_until` | null | 쿨다운 종료 시각 (로컬 시간) |

### Security Implementation

- **세션**: `SESSION_SECRET_KEY = sha256(DASHBOARD_PASSWORD)` — 쿠키 값으로 사용
- **CSRF**: `CSRF_SECRET = secrets.token_hex(32)` — 서버 기동 시 생성, 홈 렌더링 시 context로 전달
  - 프론트엔드에서 `X-CSRF-Token` 헤더로 모든 POST 요청에 포함
- **Rate Limiting**: `LOGIN_ATTEMPTS[ip] = {count, blocked_until}` — 인메모리, 재시작 시 초기화
- **보안 헤더**: CSP는 Tailwind CDN / jsdelivr / Google Fonts 허용, `unsafe-inline` 허용 (인라인 스크립트 존재)

### API Endpoints

세션 쿠키 필수. POST는 `X-CSRF-Token` 헤더 필수.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/status` | 세션 | 잔고, 지표, 거래내역, 설정, 통계 전체, candle_data(15분봉 50개) |
| POST | `/api/settings` | 세션+CSRF | 거래 설정 업데이트 (Pydantic 검증) |
| POST | `/api/toggle` | 세션+CSRF | 봇 시작/정지 |
| POST | `/api/sell_now` | 세션+CSRF | 즉시 전량 매도 |

### UI Layout

```
[Header]
[Balance Bar] — 잔고, 보유 수량, 거래 단계/필터 블로킹 상태, 거래 설정 버튼
[Yield Bar]   — 전폭 파란 바. 수익률%, 미실현₩, 코인명, 현재가/평단가, 즉시매도
[BTC 15분봉 차트 | 누적수익 히스토리] — 각 span 6, 나란히 배치
[스탯 카드 7개] — RSI 충족 시 필터 뱃지(✓/✗) 표시
[거래내역 테이블]
```

**필터 블로킹 UI:**
- 상태 바 `trade-phase-text`: RSI 충족 + 필터 미달 시 `RSI 충족 — 필터 대기` (주황색)
- 상태 바 `trade-phase-sub`: `블로킹: 볼린저(밴드 내부)` 등 구체적 필터명 표시
- RSI 카드 `#filter-badges`: 활성 필터만 `볼린저 ✗` / `MACD ✓` 뱃지로 표시 (포지션 없을 때만)

**BTC 실시간 차트 (`#candleChart`):**
- `initCandleChart()`: 4개 dataset — High(fill), Low(fill base), Close(yellow line), Bollinger Lower(blue dash)
- `updateStatus()`에서 `data.candle_data`로 매 3초 갱신, `candleChart.update('none')`으로 애니 없이 빠른 업데이트

### UI Hint System

스탯 카드 및 설정 모달의 `?` 버튼 구현:

- **`.hint-btn`**: `position:absolute; top:0; right:0` — 카드 우측 상단 모서리 고정
- **`.cfg-hint-btn`**: 인라인 원형 버튼 — 모달 label 옆
- **`showHint(key, btn)`**: `hintData[key][lang]` 조회 → `<dialog id="hint-popup">.showModal()` 호출
  - `showModal()`로 브라우저 top layer에 올려 `<dialog>` config-modal 위에 표시
  - `requestAnimationFrame` 내에서 `getBoundingClientRect()`로 버튼 기준 위치 계산
  - 화면 경계 넘침 자동 보정
- **`closeHint()`**: `popup.close()`
- `hintData`에 `yield_bar` + 7개 스탯 카드 + 11개 설정 항목 한/영 설명 포함
