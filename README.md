# BITRADE CORE

빗썸 API를 활용한 비트코인 자동 매매 웹 대시보드입니다. RSI + 볼린저밴드 필터 기반 분할매수 전략과 ATR 동적 손절, 트레일링 익절, 리스크 관리 시스템을 탑재합니다.

## 주요 기능

- **매수 필터**: RSI + 볼린저밴드 하단 기본, MACD 반전 / 거래량 급증 필터 토글 가능
- **분할매수**: 1차 진입(잔고 60%) 후 추가 하락 시 2차 추가매수로 평단 낮추기
- **ATR 동적 손절**: 시장 변동성에 따라 손절폭 자동 조정 (-0.5 ~ -3.0%)
- **트레일링 익절**: 목표 수익률 도달 후 고점 대비 일정 폭 하락 시 자동 매도
- **리스크 관리**: 일일 손실 한도 자동 정지 + 연속 손절 쿨다운
- **즉시매도 버튼**: 대시보드에서 수동 전량 매도
- **실시간 대시보드**: Bauhaus 디자인 UI, 누적수익 차트, 볼린저/MACD/거래량 실시간 카드
  - 스탯 카드 각 항목에 `?` 힌트 버튼 — 지표 설명 팝업 (한/영 언어 연동)
  - 거래 설정 모달 각 항목에 `?` 힌트 버튼 — 파라미터 설명 팝업
- **수수료 추적**: 거래별 수수료 기록 및 순익 반영 (빗썸 0.04% 쿠폰 기준)
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
| 2 | 트레일링 익절 (목표% 도달 후 offset% 하락) | 전량 시장가 매도 |
| - | 즉시매도 버튼 | 수동 전량 매도 |

### 리스크 관리

| 기능 | 기본값 | 설명 |
|---|---|---|
| 일일 손실 한도 | -50,000 ₩ | 초과 시 봇 자동 정지 |
| 연속 손절 쿨다운 | 3회 → 60분 | N회 연속 손절 시 매수 금지 |
| ATR 손절 범위 | -0.5 ~ -3.0% | 변동성 낮으면 좁게, 높으면 넓게 |

모든 수치는 대시보드 거래 설정에서 실시간 변경 가능합니다.

### 수수료

| 거래소 | 요율 | 비고 |
|---|---|---|
| 빗썸 | 0.04% | 수수료 쿠폰 적용 (30일 갱신 필요) |
| 업비트 | 0.05% | UI 비활성화 상태 |

- BUY 수수료: 매수금액 × 0.04%
- SELL 수수료: 매도금액 × 0.08% (매수+매도 양쪽 합산)
- 앱 재시작 시 전체 거래 수수료 자동 소급 재계산

## 파일 구조

```
main.py                 FastAPI 앱, API 라우트, 트레이딩 루프, 리스크 관리, 보안
models.py               SQLAlchemy ORM (TradeHistory, BotSettings)
config.py               .env 로드
core/
  strategy.py           RSI, 볼린저, MACD, 거래량, ATR 지표 계산
  bithumb_client.py     빗썸 V1 JWT/SHA512 클라이언트
  upbit_client.py       pyupbit 래퍼 (현재 비활성화)
  discord_notifier.py   웹훅 알림
templates/index.html    Tailwind + Chart.js 대시보드
static/css/bauhaus.css  Bauhaus 디자인 시스템
```

## 환경 변수 (.env)

```
BITHUMB_ACCESS_KEY=
BITHUMB_SECRET_KEY=
DISCORD_WEBHOOK_URL=
DASHBOARD_PASSWORD=
EXCHANGE=BITHUMB
SYMBOL=KRW-BTC
```

## 주의사항

본 소프트웨어는 개인 용도로 제작되었으며, 투자 결과에 대한 책임은 사용자 본인에게 있습니다. 실제 자산 운용 전 충분한 테스트를 권장합니다.
