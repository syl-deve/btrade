# BITRADE CORE

빗썸 API를 활용한 비트코인 자동 매매 웹 대시보드입니다. RSI + 볼린저밴드 필터 기반 분할매수 전략과 ATR 동적 손절, 트레일링 익절, 리스크 관리 시스템을 탑재합니다.

## 주요 기능

- **매수 필터**: RSI + 볼린저밴드 하단 기본, MACD 반전 / 거래량 급증 필터 토글 가능
- **분할매수**: 1차 진입(잔고 60%) 후 추가 하락 시 2차 추가매수로 평단 낮추기
- **ATR 동적 손절**: 시장 변동성에 따라 손절폭 자동 조정 (-0.5 ~ -3.0%)
- **트레일링 익절**: 목표 수익률 도달 후 고점 대비 일정 폭 하락 시 자동 매도
- **추세 익절 보류**: 트레일링 익절이 발동해도 EMA, Chandelier Stop, MACD가 강한 추세를 보이면 계속 보유
- **리스크 관리**: 일일 손실 한도 자동 정지 + 연속 손절 쿨다운
- **즉시매도 버튼**: 대시보드에서 수동 전량 매도
- **실시간 대시보드**: Bauhaus 디자인 UI
  - 전폭 수익률 바: 실시간 수익률%, 미실현 손익, 현재가/평단가, 즉시매도 버튼
  - BTC 15분봉 실시간 차트 (close 라인 + 고가/저가 범위 + 볼린저 하단선)
  - 누적수익 히스토리 차트 최근 30건 표시 (두 차트 나란히 배치)
  - 스탯 카드 7개: RSI 충족 시 필터별 통과/실패 뱃지(✓/✗) 표시
  - 상태 바: 필터 블로킹 시 어떤 필터가 막히는지 명시 (`RSI 충족 — 필터 대기`)
  - 스탯 카드·설정 모달 각 항목에 `?` 힌트 버튼 — 지표/파라미터 설명 팝업 (한/영 언어 연동)
- **수수료 추적**: 거래별 수수료 기록 및 순익 반영 (빗썸 0.04% 쿠폰 기준, 빗썸 앱 기준과 일치)
- **보안**: 로그인 Rate Limiting (5회 실패 시 10분 차단), CSRF 토큰, 보안 헤더
- **디스코드 알림**: 매수/매도/손실한도/쿨다운 이벤트 즉시 알림
- **한/영 UI 토글**

## 설치 및 실행

```bash
# 1. 가상환경 생성 및 패키지 설치
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 2. 환경 변수 설정
cp .env.template .env        # .env 파일을 열어 API 키 입력
python3 scratch/generate_admin_hash.py  # 관리자 비밀번호 해시 생성 후 .env에 입력

# 3. 서버 실행
python main.py               # http://localhost:8000
```

## 매매 전략

### 매수 조건

| 필터 | 조건 | 토글 |
|---|---|---|
| RSI | ≤ 35 (1차) / ≤ 28 (2차) | 항상 적용 |
| 볼린저밴드 | 현재가 ≤ 하단 밴드 (20기간, 2σ) | `use_bollinger` |
| MACD | 히스토그램 음수 구간 반전 (12/26/9) | `use_macd` |
| 거래량 | 20봉 평균의 N배 이상 | `use_volume_filter` |

- 활성화된 필터 전부 통과 시 → 잔고 × `first_buy_ratio`(60%) 매수
- **2차 추가매수**: RSI ≤ 28 AND 현재가 < 평단 → 잔여 잔고 전량 매수

### 매도 조건 (우선순위 순)

| 순위 | 조건 | 행동 |
|---|---|---|
| 1 | ATR 동적 손절 도달 (-0.5 ~ -3.0%) | 전량 시장가 매도 |
| 2 | 트레일링 익절 + 추세 확인 | 추세 강하면 보유, 추세 약화 시 전량 시장가 매도 |
| - | 즉시매도 버튼 | 수동 전량 매도 |

#### 추세 익절 보류

`use_trend_exit=true`이면 목표 수익률 도달 후 트레일링 되돌림이 발생해도 아래 조건이 모두 유지되는 동안 매도를 보류합니다.

- 현재가가 `EMA(trend_ema_period)` 위에 있음
- 현재가가 `Chandelier Stop` 위에 있음
- MACD histogram이 `macd_weak_confirm_candles`개 봉 연속 약화 중이 아님

조건이 깨지면 기존 트레일링 익절 매도가 허용됩니다. ATR 손절은 이 로직보다 우선순위가 높아서 즉시 매도할 수 있습니다.

### 리스크 관리

| 기능 | 기본값 | 설명 |
|---|---|---|
| 일일 손실 한도 | -50,000 ₩ | 초과 시 봇 자동 정지 |
| 연속 손절 쿨다운 | 2회 → 60분 | N회 연속 손절 시 매수 금지 |
| ATR 손절 범위 | -0.5 ~ -3.0% | 변동성 낮으면 좁게, 높으면 넓게 |
| ATR 비활성화 | use_atr=false | ATR 무시, 설정한 손절율 그대로 사용 |

모든 수치는 대시보드 거래 설정에서 실시간 변경 가능합니다.

#### 쿨다운 동작 상세

- 쿨다운 만료 후 `cooldown_until`을 현재 시각으로 갱신 → 그 이후 발생한 SELL만 연속 손절 카운트
- 과거 손절 내역이 쿨다운 만료 시 재감지되는 무한루프 방지
- 쿨다운 중 대시보드 거래 단계 섹션에 `⏸ 쿨다운 N분 남음` 표시
- DB 직접 해제: `UPDATE bot_settings SET cooldown_until = NULL`

### 수수료

빗썸 수수료 쿠폰 적용 기준 (30일 갱신 필요):

- BUY 수수료: 매수금액 × 0.04%
- SELL 수수료: 매도금액 × 0.04% (거래 내역 표시 기준, 빗썸 앱과 일치)
- 순익(net_profit) 계산: 매도금액 - 매수원금 - (매수 수수료 + 매도 수수료)
- 앱 재시작 시 전체 거래 수수료 자동 소급 재계산

## 파일 구조

```
main.py                 FastAPI 앱, API 라우트, 트레이딩 루프, 리스크 관리, 보안
models.py               SQLAlchemy ORM (TradeHistory, BotSettings)
config.py               .env 로드
core/
  strategy.py           RSI, 볼린저, MACD, 거래량, ATR 지표 계산
  bithumb_client.py     빗썸 V1 JWT/SHA512 클라이언트
  discord_notifier.py   웹훅 알림
templates/index.html    Tailwind + Chart.js 대시보드 (PWA 지원)
static/
  css/bauhaus.css       Bauhaus 디자인 시스템
  manifest.json         PWA 앱 메타데이터
  sw.js                 Service Worker (정적 자산 캐싱)
  icons/                PWA 아이콘 (192x192, 512x512, SVG)
notify-ngrok.sh         ngrok 주소 디스코드 알림 스크립트
```

## 배포 (AWS EC2)

### HTTPS 설정 (PWA 동작 필수)

Service Worker는 HTTPS 환경에서만 동작합니다. ngrok으로 HTTPS 터널을 구성합니다.

```bash
# 1. ngrok 설치
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# 2. 인증 토큰 등록 (https://dashboard.ngrok.com 에서 발급)
ngrok config add-authtoken <TOKEN>
```

ngrok systemd 서비스 (`/etc/systemd/system/ngrok.service`):

```ini
[Unit]
Description=ngrok tunnel
After=network.target bitrade.service

[Service]
Type=simple
User=ec2-user  # 실행할 사용자 계정명으로 변경 (GCP인 경우 예: mythe82)
ExecStart=/usr/local/bin/ngrok http 8000 --log=stdout
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok
sudo systemctl start ngrok
```

재시작 시 새 ngrok 주소를 디스코드로 자동 알림:

```bash
# ngrok-notify systemd 서비스 등록
sudo tee /etc/systemd/system/ngrok-notify.service > /dev/null << 'EOF'
[Unit]
Description=ngrok URL notify to Discord
After=ngrok.service

[Service]
Type=oneshot
User=ec2-user  # 실행할 사용자 계정명으로 변경 (GCP인 경우 예: mythe82)
ExecStart=/home/ec2-user/btrade/notify-ngrok.sh  # 본인 계정 경로에 맞게 변경 (예: /home/mythe82/btrade/...)

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ngrok-notify
```

현재 ngrok 주소 확인:

```bash
curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json;print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

### PWA 설치

HTTPS 주소로 접속 후:

- **Android Chrome**: 주소창 메뉴 → "홈 화면에 추가"
- **iOS Safari**: 공유 버튼 → "홈 화면에 추가"

## 환경 변수 (.env)

```
BITHUMB_ACCESS_KEY=
BITHUMB_SECRET_KEY=
DISCORD_WEBHOOK_URL=
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=pbkdf2_sha256$260000$...
VIEWER_USERNAME=viewer
VIEWER_PASSWORD_HASH=pbkdf2_sha256$260000$...
SYMBOL=KRW-BTC
```

관리자 비밀번호는 원문을 저장하지 않습니다. 아래 명령으로 해시를 생성한 뒤 `ADMIN_PASSWORD_HASH`에 넣으세요.

```bash
python3 scratch/generate_admin_hash.py  # Linux/EC2
python scratch/generate_admin_hash.py   # Windows
```

`ADMIN_PASSWORD_HASH`가 설정되지 않은 경우에만 기존 `DASHBOARD_PASSWORD` fallback을 임시로 사용할 수 있습니다. 운영 환경에서는 `DASHBOARD_PASSWORD`를 제거하거나 주석 처리하세요.

### Viewer account

Set the external read-only account with `VIEWER_USERNAME` and `VIEWER_PASSWORD_HASH`. Generate the hash with the same helper used for the admin password:

```bash
python3 scratch/generate_admin_hash.py  # Linux/EC2
python scratch/generate_admin_hash.py   # Windows
```

The viewer account can open the dashboard and read `/api/status`, including the same balances, settings, and trade history visible to the admin. It cannot save trading settings, start or stop the bot, or run instant sell. Direct viewer requests to `/api/settings`, `/api/toggle`, and `/api/sell_now` return `403 Forbidden`.

### Server update

After pulling this change on the server, add the viewer hash to `.env` and restart the app:

```bash
git pull origin main
python3 scratch/generate_admin_hash.py
# Put the generated hash in VIEWER_PASSWORD_HASH.
sudo systemctl restart bitrade  # if running with systemd
```

## Architecture

### Data Flow

1. FastAPI 앱 시작 → `_run_db_migrations()` 즉시 실행 (모듈 로드 시) → SQLite 컬럼 자동 추가 + fee 소급 적용
2. Background `trading_loop()` 60초마다 실행
3. OHLCV 조회 → 지표 계산 → 매수/매도 판단 → DB 기록 → Discord 알림

### Key Files

- **`main.py`**: FastAPI 앱, 인증, API 라우트, 트레이딩 루프
  - `_run_db_migrations()`: 모듈 로드 시 즉시 실행. fee가 NULL인 레코드만 소급 적용 (중복 실행 방지). BUY fee = `total_amount × 0.0004`, SELL fee = `total_amount × 0.0004` (매도 단건 기준, 빗썸 앱 일치)
  - `_reset_position()`: avg_buy_price, highest_profit_rate, buy_count, position_opened_at 초기화
  - `_record_sell()`: 매도 기록. DB fee = 매도금액×0.04% (단건, 빗썸 앱 기준). net_profit = 매도금액 - 매수원금 - (매수+매도 수수료 합산). `_reset_position` 호출. `/api/sell_now`도 이 함수 재사용
  - `_record_buy()`: 매수 기록. fee = 매수금액×0.04%
  - `_check_daily_loss()`: 당일 net_profit 합계 ≤ daily_loss_limit → is_running = False
  - `_check_consecutive_loss()`: 쿨다운 만료 시점 이후 SELL만 카운트 → cooldown_until 설정 (로컬 시간). 만료 직후 cooldown_until을 now로 갱신하여 과거 손절 재감지 방지
  - ATR 동적 손절: `use_atr=True`면 ATR×배수 계산값 사용, `False`면 `stop_loss_rate` 고정값 사용
  - `get_fee_rate()`: BITHUMB_FEE_RATE = 0.0004 고정 반환
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
  - `get_ema()`: 추세 익절 보류용 EMA 계산
  - `get_chandelier_stop()`: 최근 고점 - ATR×배수 방식의 Chandelier Stop 계산
  - `get_trend_exit_state()`: EMA, Chandelier Stop, MACD 약화 여부를 종합해 `trend_ok` 반환
  - `/api/status`: 지표(RSI/볼린저/MACD/거래량)·캔들 데이터는 `indicator_exchange = "BITHUMB"`으로 고정 조회 (public API, 인증 불필요). `strategy=None` 시 `ScalperStrategy()` fallback 생성. 현재가 실패 시 `bithumb_client.get_current_price()` fallback
  - `candle_data`: 빗썸 OHLCV DataFrame은 인덱스가 정수, 시각은 `candle_date_time_kst` 컬럼 → `strftime` 직접 호출 불가. `candle_date_time_kst` → `candle_date_time_utc` → `timestamp` 컬럼 순서로 탐색
- **`core/strategy.py`**: 모든 지표 계산
  - `get_ohlcv()`: `BithumbClient.get_ohlcv()` 직접 호출 (빗썸 단일 거래소)
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
| `use_atr` | True | ATR 동적 손절 사용 여부. False 시 stop_loss_rate 고정 사용 |
| `use_trend_exit` | True | 트레일링 익절 발동 후 추세가 강하면 매도 보류 |
| `trend_ema_period` | 20 | 추세 유지 판단용 EMA 기간 |
| `chandelier_atr_multiplier` | 2.5 | Chandelier Stop 계산에 쓰는 ATR 배수 |
| `macd_weak_confirm_candles` | 2 | MACD histogram 연속 약화 확인 봉 수 |
| `max_hold_hours` | 4.0 | DB 컬럼 존재, 강제 청산 비활성화 |
| `daily_loss_limit` | -50000 | 일일 손실 한도 (원) |
| `max_consecutive_loss` | 3 | 연속 손절 허용 횟수 |
| `cooldown_minutes` | 60 | 쿨다운 시간 (분) |
| `cooldown_until` | null | 쿨다운 종료 시각 (로컬 시간) |

### Security Implementation

Current dashboard authentication supports administrator and read-only viewer accounts:

- **Admin credentials**: `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH`
- **Viewer credentials**: `VIEWER_USERNAME` + `VIEWER_PASSWORD_HASH`
- **Viewer access**: can read the dashboard and `/api/status`; cannot call write/execute APIs
- **Password storage**: PBKDF2-SHA256 hash generated by `scratch/generate_admin_hash.py`; do not store the raw password in `.env`
- **Session cookie**: random server-side session token, stored as `HttpOnly`, `SameSite=Lax`; `Secure` is enabled on HTTPS requests
- **Login throttling**: `LOGIN_ATTEMPTS[ip:username]` blocks an IP/account pair for 10 minutes after 5 failures

- **CSRF**: `CSRF_SECRET = secrets.token_hex(32)` — 서버 기동 시 생성, 홈 렌더링 시 context로 전달
  - 프론트엔드에서 `X-CSRF-Token` 헤더로 모든 POST 요청에 포함
- **보안 헤더**: CSP는 Tailwind CDN / jsdelivr / Google Fonts 허용, `unsafe-inline` 허용 (인라인 스크립트 존재)

### API Endpoints

세션 쿠키 필수. POST는 `X-CSRF-Token` 헤더 필수.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/status` | 세션 | 잔고, 지표, 거래내역, 설정, 통계 전체, candle_data(15분봉 50개) |
| POST | `/api/settings` | 세션+CSRF | 거래 설정 업데이트 (Pydantic 검증) |
| POST | `/api/toggle` | 세션+CSRF | 봇 시작/정지 |
| POST | `/api/sell_now` | 세션+CSRF | 즉시 전량 매도 |

Viewer sessions are allowed only on `GET /` and `GET /api/status`. The write/execute endpoints require an admin session and CSRF token; viewer sessions receive `403 Forbidden`.

`GET /api/status` also returns trend-exit state for the dashboard:

- `highest_profit_rate`: current position peak profit rate used by trailing exit
- `trend_exit.enabled`: whether trend-aware exit hold is active
- `trend_exit.trend_ok`: true when EMA, Chandelier Stop, and MACD checks still support holding
- `trend_exit.ema`, `trend_exit.chandelier_stop`, `trend_exit.macd_weak`: detail values used for the phase label

### UI Layout

```
[Header]
[Balance Bar] — 잔고, 보유 수량, 거래 단계/필터 블로킹 상태, 거래 설정 버튼
[Yield Bar]   — 전폭 파란 바. 수익률%, 미실현₩, 코인명, 현재가/평단가, 즉시매도
[BTC 15분봉 차트 | 누적수익 히스토리] — 각 span 6, 나란히 배치
[스탯 카드 7개] — RSI 충족 시 필터 뱃지(✓/✗) 표시
[거래내역 테이블]
```

The Balance Bar phase label shows trend-aware exit states:

- `TREND HOLD`: target profit is armed, trailing pullback occurred, but trend checks still support holding
- `TREND WEAKNESS WATCH`: target profit is armed and trend checks weakened, so the next trailing pullback can sell

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

## 주의사항

본 소프트웨어는 개인 용도로 제작되었으며, 투자 결과에 대한 책임은 사용자 본인에게 있습니다. 실제 자산 운용 전 충분한 테스트를 권장합니다.
