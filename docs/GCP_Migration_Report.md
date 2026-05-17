# AWS EC2 to GCP Compute Engine 마이그레이션 완료 보고서

본 문서는 Bitrade 자동 스캘핑 봇 및 대시보드 서비스를 AWS EC2에서 GCP Compute Engine으로 안전하게 마이그레이션한 전체 과정과 발생한 트러블슈팅 이력 및 운영 가이드를 정리한 통합 보고서입니다.

---

## 1. 마이그레이션 개요

- **목적**: 기존 AWS EC2 운영 환경을 GCP Compute Engine(Ubuntu 24.04 LTS) 인프라로 이전하여 안정성 및 운영 효율성 극대화
- **이전 대상**:
  - Bitrade 웹 대시보드 및 백그라운드 트레이딩 루프 (`main.py`)
  - SQLite 데이터베이스 (`trading_bot.db` - 과거 거래 내역 및 설정값 포함)
  - ngrok 보안 터널링 시스템 및 디스코드 알림 연동 모듈
- **수행 결과**: 이전 완료 및 빗썸 API 실시간 거래 연동 검증 완료

---

## 2. 시스템 구성도

GCP Compute Engine 환경으로 이전된 Bitrade 시스템의 서비스 흐름도입니다.

```mermaid
graph TD
    subgraph GCP Compute Engine (Ubuntu 24.04)
        A[Bitrade Service / main.py] -->|SQLite| B[(trading_bot.db)]
        A -->|Port 8000| C[Uvicorn Web Server]
        D[ngrok Service] -->|Local Tunneling| C
        E[notify-ngrok.sh / Oneshot] -->|Check Local API Port 4040| D
    end

    subgraph External Services
        F[Discord Webhook] <--|Send Address URL| E
        G[User Web Browser] -->|HTTPS Access| D
        A -->|Private API Authentication| H[Bithumb Exchange]
    end

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#bbf,stroke:#333,stroke-width:2px
    style H fill:#fbb,stroke:#333,stroke-width:2px
```

---

## 3. 단계별 마이그레이션 수행 이력

### [x] 1단계. 데이터 백업 및 GCP 전송
- AWS EC2 환경에서 기존 프로젝트 폴더(`btrade/`) 전체를 Tar 아카이브로 압축 백업하였습니다.
- GCP Compute Engine 인스턴스 정보(`35.209.133.249`, 계정명: `mythe82`)를 수령하였습니다.
- AWS 인스턴스 내부에서 임시 SSH 키를 생성하여 GCP 프로젝트 메타데이터에 등록한 뒤, SCP를 통해 압축본(`btrade.tar`)을 GCP 인스턴스 홈 디렉토리(`/home/mythe82/`)로 직접 고속 전송하고 해제하였습니다.

### [x] 2단계. 실행 사용자 및 가상환경 맞춤 서비스 스크립트화
- 기존 `ec2-user` 사용자명과 특정 절대 경로로 하드코딩되어 있던 `setup_service.sh` 스크립트를 고도화하였습니다.
- `$(whoami)` 및 `$(pwd)`를 동적으로 감지하여 GCP 사용자(`mythe82`)와 작업 디렉토리 경로(`/home/mythe82/btrade`)에 맞는 `bitrade.service`를 자동 빌드하도록 수정하고 원격 Git에 배포 및 실행하였습니다.

### [x] 3단계. ngrok 터널링 및 알림 연동 구축
- Ubuntu 패키지 관리자(APT)를 통해 공식 ngrok 패키지를 안정적으로 설치하였습니다.
- 터널링을 제어하기 위한 `ngrok.service`와 부팅 시 터널링 주소를 파싱하여 디스코드로 쏘아주는 `ngrok-notify.service` (Oneshot 서비스) 구조를 설계하고 시스템 데몬에 등록하였습니다.

---

## 4. 주요 트러블슈팅 및 해결 이력

마이그레이션 과정 중 발생했던 주요 장애 요인과 이를 해결한 핵심 조치 이력입니다.

### 1) ngrok 서비스 `status 203/EXEC` 실행 실패
- **증상**: ngrok 서비스 시작 시 실행 바이너리를 찾지 못해 `203/EXEC` 코드로 즉시 크래시 발생
- **원인**: APT로 설치된 실제 ngrok의 경로는 `/usr/local/bin/ngrok`이었으나 서비스 파일에 `/usr/bin/ngrok`로 하드코딩되어 발생
- **조치**: `which ngrok`로 실제 설치 위치를 검증한 후 서비스 설정 파일의 `ExecStart` 경로를 정확히 교정하여 해결

### 2) ngrok 서비스 `status 1/FAILURE` 인자값 오류
- **증상**: ngrok이 실행 인자 개수 오류(`You specified 9 arguments`)를 뱉으며 무한 재시작 루프에 빠짐
- **원인**: systemd 서비스 파일은 `ExecStart` 명령어 라인 뒤에 적힌 샵(`#`) 기호 주석까지 전부 실행 인자값으로 프로그램에 전달하므로, 설명 주석 전체가 오인식됨
- **조치**: 서비스 파일 내부의 인라인 주석 처리를 완전히 제거한 순수 명령어로 재작성하고 데몬을 리로드하여 정상 작동 완료

### 3) ngrok 인증 토큰 오류 (`ERR_NGROK_105`)
- **증상**: 세션 수립 단계에서 올바르지 않은 토큰 형식으로 연결 거부
- **원인**: 타 서비스의 인증키 문자열이 ngrok 토큰 자리에 등록되어 발생
- **조치**: ngrok 대시보드에서 정식 발급된 클래식 토큰 문자열을 수집하여 `ngrok config add-authtoken`으로 재등록 완료

### 4) `.env` 파일 내 해시 문자열 파싱 오류
- **증상**: 기존 해시를 그대로 붙여넣었음에도 대시보드 로그인 시 `INVALID CREDENTIALS` 발생
- **원인**: 비밀번호 해시값 내에 포함된 `$` 기호들을 `python-dotenv` 라이브러리가 환경 변수 치환 문자로 오인하여 해시 일부분을 누락시킨 채 로드함
- **조치**: `.env` 파일 내의 `ADMIN_PASSWORD_HASH` 및 `VIEWER_PASSWORD_HASH` 값을 작은따옴표(`'`)로 확실하게 감싸서 변수 치환 현상을 예방하고, 사용자가 입력하는 비밀번호에 100% 대응되도록 `generate_admin_hash.py`를 활용해 신규 해시값을 등록하여 로그인 성공

### 5) 빗썸 API "IP 허용 차단" (`NotAllowIP`)
- **증상**: 대시보드는 로그인되었으나 백그라운드 봇이 빗썸 잔고 조회 실패 경고를 반복하며 거래하지 못함
- **원인**: AWS EC2에서 GCP로 마이그레이션됨에 따라 서버의 외부 공인 IP가 변경되어, 기존 빗썸 API Key의 IP 화이트리스트 정책에 의해 거부됨
- **조치**: 빗썸 API 관리 콘솔에 접속하여 새로운 GCP 외부 공인 IP인 **`35.209.133.249`**를 허용 IP 대역으로 수정 등록하여 실시간 거래 원장 동기화에 성공

---

## 5. 서비스 관리 및 운영 가이드

이전 완료된 GCP 서버에서 서비스를 제어하기 위해 사용하는 핵심 명령어 사전입니다.

### 1) 봇 및 대시보드 서버 제어
```bash
# 서비스 상태 확인
sudo systemctl status bitrade

# 서비스 재시작 (코드 또는 .env 수정 시 필수)
sudo systemctl restart bitrade

# 실시간 작동 로그 모니터링
tail -f -n 50 /home/mythe82/btrade/trading.log
```

### 2) ngrok 터널링 및 알림 제어
```bash
# 터널링 상태 확인
sudo systemctl status ngrok

# 터널링 주소 강제 디스코드 재전송
/home/mythe82/btrade/notify-ngrok.sh
```

---

본 마이그레이션을 통해 서비스 인프라 안정성이 대폭 상향되었으며, 향후 GCP 환경에서의 효율적 운영이 기대됩니다.
