import requests

BASE_URL = "http://localhost:8000"

def test_unauthorized_access():
    print("\n[1. 인증 없이 데이터 요청 테스트]")
    res = requests.get(f"{BASE_URL}/api/status")
    if res.status_code == 401:
        print("✅ 성공: 인증 없이 접근 시 401 Unauthorized로 차단됨.")
    else:
        print(f"❌ 실패: 인증 없이 접근 성공 (Status: {res.status_code})")

def test_csrf_protection():
    print("\n[2. CSRF 토큰 없이 POST 요청 테스트]")
    # 로그인을 시뮬레이션하여 세션 쿠키 획득 (서버가 실행 중이고 비밀번호가 맞아야 함)
    # 여기서는 토큰 검증 로직이 작동하는지만 확인하기 위해 헤더를 누락시키고 보냅니다.
    res = requests.post(f"{BASE_URL}/api/toggle")
    if res.status_code == 403:
        print("✅ 성공: CSRF 토큰 누락 시 403 Forbidden으로 차단됨.")
    else:
        print(f"❌ 실패: CSRF 토큰 없이 POST 요청 성공 (Status: {res.status_code})")

if __name__ == "__main__":
    try:
        test_unauthorized_access()
        test_csrf_protection()
    except Exception as e:
        print(f"오류: 서버가 실행 중인지 확인하세요. ({e})")
