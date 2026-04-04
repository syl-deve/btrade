# BITRADE CORE

업비트/빗썸 API를 활용한 비트코인 자동 매매 웹 대시보드입니다. RSI + 볼린저밴드 기반 분할매수 전략으로 24시간 운용에 최적화되어 있습니다.

## 주요 기능

- **자동 매매 전략**: RSI + 볼린저밴드 하단 조건 결합, 2단계 분할매수, 트레일링 익절
- **실시간 대시보드**: Bauhaus 디자인 UI, 누적수익 차트, 분할매수 포지션 현황, 즉시매도 버튼
- **멀티 거래소**: 업비트 / 빗썸 전환 지원 (`.env` 설정)
- **디스코드 알림**: 매수/매도/에러 발생 시 웹훅 즉시 알림
- **한/영 UI 토글**: 전체 인터페이스 언어 전환 지원

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

| 단계 | 조건 | 행동 |
|---|---|---|
| 1차 매수 | RSI ≤ 35 AND 볼린저 하단 이탈 | 잔고 60% 시장가 매수 |
| 2차 매수 | RSI ≤ 28 AND 현재가 < 평단 | 잔고 전량 추가매수, 평단 재계산 |
| 트레일링 익절 | 수익률 ≥ 1.5% 도달 후 0.3% 하락 | 전량 시장가 매도 |
| 긴급 손절 | 수익률 ≤ -1% | 즉시 전량 매도 |
| 즉시매도 | 대시보드 버튼 클릭 | 수동 전량 매도 |

모든 수치는 대시보드 거래 설정에서 실시간 변경 가능합니다.

## 파일 구조

```
main.py                 FastAPI 앱, 인증, API 라우트, 트레이딩 루프
models.py               SQLAlchemy ORM (TradeHistory, BotSettings)
config.py               .env 로드
core/
  strategy.py           RSI + 볼린저밴드 계산
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
