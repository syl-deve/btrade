# BITRADE CORE

업비트/빗썸 API를 활용한 비트코인 자동 매매 웹 대시보드입니다. RSI + 볼린저밴드 + MACD + 거래량 4중 필터 기반 분할매수 전략과 ATR 동적 손절, 리스크 관리 시스템을 탑재합니다.

## 주요 기능

- **4중 필터 매수**: RSI + 볼린저밴드 하단 + MACD 반전 + 거래량 급증 동시 충족 시 진입
- **분할매수**: 1차 진입(잔고 60%) 후 추가 하락 시 2차 추가매수로 평단 낮추기
- **ATR 동적 손절**: 시장 변동성에 따라 손절폭 자동 조정 (-0.5 ~ -3.0%)
- **리스크 관리**: 일일 손실 한도 자동 정지 + 연속 손절 쿨다운
- **보유시간 강제청산**: 설정 시간 초과 + 손실 중이면 자동 매도
- **즉시매도 버튼**: 대시보드에서 수동 전량 매도
- **실시간 대시보드**: Bauhaus 디자인 UI, 누적수익 차트, 분할매수 포지션 현황
- **멀티 거래소**: 업비트 / 빗썸 전환 지원
- **디스코드 알림**: 매수/매도/손실한도/쿨다운 이벤트 즉시 알림
- **한/영 UI 토글**

## 설치 및 실행

```bash
# 1. 가상환경 생성 및 패키지 설치
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt

# 2. 환경 변수 설정
copy .env.template .env      # .env 파일을 열어 API 키 입력

# 3. 서버 실행
python main.py               # http://localhost:8000
```

## 매매 전략

### 매수 조건 (4중 필터, 모두 충족 시 진입)

| 필터 | 조건 | 비고 |
|---|---|---|
| RSI | ≤ 35 (1차) / ≤ 28 (2차) | 14기간, 15분봉 |
| 볼린저밴드 | 현재가 ≤ 하단 밴드 | 20기간, 2σ |
| MACD | 히스토그램 음수 구간 반전 | 12/26/9, 바닥 다지는 시점 |
| 거래량 | 20봉 평균의 1.5배 이상 | 급등 초입 포착 |

### 매도 조건 (우선순위 순)

| 순위 | 조건 | 행동 |
|---|---|---|
| 1 | ATR 동적 손절 도달 | 전량 시장가 매도 |
| 2 | 보유시간 초과 + 손실 중 | 강제 청산 |
| 3 | 트레일링 익절 (1.5% 도달 후 0.3% 하락) | 전량 시장가 매도 |
| - | 즉시매도 버튼 | 수동 전량 매도 |

### 리스크 관리

| 기능 | 기본값 | 설명 |
|---|---|---|
| 일일 손실 한도 | -50,000 ₩ | 초과 시 봇 자동 정지 |
| 연속 손절 쿨다운 | 3회 → 60분 | N회 연속 손절 시 매수 금지 |
| ATR 손절 범위 | -0.5 ~ -3.0% | 변동성 낮으면 좁게, 높으면 넓게 |

모든 수치는 대시보드 거래 설정에서 실시간 변경 가능합니다.

## 파일 구조

```
main.py                 FastAPI 앱, API 라우트, 트레이딩 루프, 리스크 관리
models.py               SQLAlchemy ORM (TradeHistory, BotSettings)
config.py               .env 로드
core/
  strategy.py           RSI, 볼린저, MACD, 거래량, ATR 지표 계산
  upbit_client.py       pyupbit 래퍼
  bithumb_client.py     빗썸 V1 JWT/SHA512 클라이언트
  discord_notifier.py   웹훅 알림
templates/index.html    Tailwind + Chart.js 대시보드
static/css/bauhaus.css  Bauhaus 디자인 시스템
```

## 환경 변수 (.env)

```
UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=
BITHUMB_ACCESS_KEY=
BITHUMB_SECRET_KEY=
DISCORD_WEBHOOK_URL=
DASHBOARD_PASSWORD=
EXCHANGE=UPBIT          # UPBIT 또는 BITHUMB
SYMBOL=KRW-BTC
```

## 주의사항

본 소프트웨어는 개인 용도로 제작되었으며, 투자 결과에 대한 책임은 사용자 본인에게 있습니다. 실제 자산 운용 전 충분한 테스트를 권장합니다.
