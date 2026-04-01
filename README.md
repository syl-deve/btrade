# 🚀 Upbit Auto-Trader (BITRADE CORE)

업비트 API를 활용한 비트코인 자동 매매 웹 대시보드입니다. 래리 윌리엄스의 변동성 돌파 전략을 기본으로 하며, 24시간 서버에서 구동하기에 최적화되어 있습니다.

## 📦 주요 기능
- **실시간 대시보드**: 모던한 다크 모드 UI와 실시간 시세 및 잔고 확인
- **자동 매매 엔진**: 래리 윌리엄스 변동성 돌파 전략 탑재 (BTC 전용)
- **실시간 알림**: 매수/매도/에러 발생 시 **디스코드 웹훅**을 통해 즉시 알림
- **보안**: 1인 전용 비밀번호 기반 접근 지원 (커스터마이징 가능)
- **로컬 DB**: SQLite를 이용한 안전한 거래 내역 저장

## 🛠️ 설치 및 시작하기

1. **사전 준비**: 
   - Python 3.9+ 가 설치되어 있어야 하며, `uv` 사용을 권장합니다.
   - 업비트 Open API에서 Access Key와 Secret Key를 발급받아야 합니다.
   - 알림을 받을 디스코드 채널의 웹훅 URL을 복사해두세요.

2. **환경 변수 설정**: 
   - `.env.template` 파일을 복사하여 `.env`로 이름을 바꿉니다.
   - 파일 안의 키 값들을 본인의 값으로 채워 넣습니다.
   ```ps1
   copy .env.template .env
   ```

3. **가상 환경 생성 및 라이브러리 설치**:
   ```ps1
   # uv를 사용하는 경우 (권장)
   uv venv
   uv pip install -r requirements.txt
   
   # 또는 기본 venv를 사용하는 경우
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **서버 실행**:
   ```ps1
   # 가상환경 활성화 상태에서
   python main.py
   ```
   - 서버가 실행되면 `http://localhost:8000`에 접속하여 대시보드를 확인할 수 있습니다.

## 📂 파일 구조
- `main.py`: FastAPI 서버 및 백그라운드 트레이딩 루프
- `config.py`: 환경 변수 로드
- `models.py`: SQLite DB 테이블 정의
- `core/`: 핵심 로직 (Upbit Client, Strategy, Discord Notifier)
- `templates/`: HTML 대시보드 UI

## ⚠️ 주의사항
- 본 소프트웨어는 개인적 용도로 제작되었으며, 투자 결과에 대한 책임은 사용자 본인에게 있습니다.
- 충분한 테스트 후 실제 자산으로 운용하시기 바랍니다.
