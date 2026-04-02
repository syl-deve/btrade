# 빗썸 API 키 발급 및 설정 가이드 (공식 문서 기반)

빗썸(Bithumb) 공식 [빠른 시작 가이드](https://apidocs.bithumb.com/docs/%EB%B9%A0%EB%A5%B8-%EC%8B%9C%EC%9E%91-%EA%B0%80%EC%9D%B4%EB%93%9C) 내용을 바탕으로 작성되었습니다.

## 1. 빗썸 API Key 발급 방법

공식 문서에 따른 발급 절차입니다.

- [ ] **계정 및 인증**: [빗썸](https://www.bithumb.com) 로그인 및 본인 인증을 완료합니다.
- [ ] **메뉴 이동**: [마이페이지 > API 관리](https://www.bithumb.com/react/api-support/management-api) 메뉴로 이동합니다.
- [ ] **권한 선택**: API 활성 항목을 필요에 맞게 선택합니다.
    - `자산조회`, `주문조회`, `주문하기`: 자동 매매 시 필수
    - `출금하기`: 보안을 위해 체크하지 않는 것을 권장합니다.
- [ ] **IP 주소 등록 (필수)**: API를 호출할 서버 또는 PC의 IP 주소를 반드시 등록해야 합니다.
- [ ] **Key 생성**: 약관 동의 후 보안 인증(SMS/OTP)을 거쳐 **[API KEY 생성]**을 완료합니다.
- [ ] **비밀 키 보관**: 화면에 표시되는 **API Key**와 **Secret Key**를 즉시 안전한 곳에 저장합니다.
    > [!CAUTION]
    > **Secret Key**는 발급 시 단 한 번만 노출됩니다. 분실 시 재발급해야 하므로 반드시 즉시 복사해 두세요.
- [ ] **활성화**: 생성된 키 리스트에서 **[활성화]** 버튼을 클릭합니다. (메일 인증 절차가 진행될 수 있습니다.)

## 2. 프로젝트 설정 (.env)

발급받은 키를 프로젝트의 환경 변수 파일에 설정합니다.

1. 프로젝트 루트의 `.env` 파일을 엽니다.
2. 아래와 같이 입력합니다 (본 프로젝트의 `config.py`와 연동됨).

```env
# Upbit API Credentials
UPBIT_ACCESS_KEY=발급받은_업비트_액세스_키
UPBIT_SECRET_KEY=발급받은_업비트_시크릿_키

# Bithumb API Credentials
BITHUMB_ACCESS_KEY=발급받은_빗썸_API_Key
BITHUMB_SECRET_KEY=발급받은_빗썸_Secret_Key

# 거래소 설정 (UPBIT 또는 BITHUMB)
EXCHANGE=BITHUMB

# 일반 설정
SYMBOL=KRW-BTC
TRADING_INTERVAL_MINUTES=1
```

## 3. 주요 참고 사항

- **인증 방식**: 빗썸 API v1은 JWT 토큰 방식의 인증을 사용합니다. 현재 프로젝트는 `pybithumb` 라이브러리를 통해 통신을 시도합니다.
- **IP 제한**: 공식 문서에서는 보안을 위해 IP 등록을 강력히 권장하며, 등록되지 않은 IP에서의 요청은 거부될 수 있습니다.
- **Rate Limit**: 빗썸 API는 요청 수 제한이 있으므로, `TRADING_INTERVAL_MINUTES` 설정을 통해 과도한 주기 호출을 방지하세요.
- **공식 API 문서**: [apidocs.bithumb.com](https://apidocs.bithumb.com/)
