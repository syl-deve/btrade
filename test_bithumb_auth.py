import sys
import os
import requests
from config import EXCHANGE, BITHUMB_ACCESS_KEY, BITHUMB_SECRET_KEY
from core.bithumb_client import BithumbClient

def test():
    print(f"현재 설정된 거래소: {EXCHANGE}")
    
    if EXCHANGE != "BITHUMB":
        print("주의: EXCHANGE가 BITHUMB으로 설정되어 있지 않습니다. (.env 확인 필요)")
    
    if not BITHUMB_ACCESS_KEY or not BITHUMB_SECRET_KEY:
        print("에러: 빗썸 API 키가 .env 파일에 설정되어 있지 않습니다.")
        return

    print("--- 빗썸 v1 API(JWT) 인증 테스트 시작 ---")
    client = BithumbClient()
    
    if client._is_authenticated:
        print("성공: 빗썸 v1 API 인증에 성공했습니다!")
        
        # 상세 잔고 확인
        headers = client._get_headers()
        res = requests.get(f"{client.api_url}/v1/accounts", headers=headers)
        if res.status_code == 200:
            accounts = res.json()
            for acc in accounts:
                if acc['currency'] == 'KRW':
                    balance = float(acc['balance'])
                    locked = float(acc.get('locked', 0))
                    print(f"현재 KRW 주문 가능: {balance:,.0f}원")
                    print(f"현재 KRW 주문 대기(락): {locked:,.0f}원")
                    print(f"현재 KRW 총합: {balance + locked:,.0f}원")
        
        # 3. 시세 조회 테스트
        price = client.get_current_price("KRW-BTC")
        if price:
            print(f"현재 BTC 가격: {price:,.0f}원")
            
        # 4. [실전 테스트] 소액 시장가 매수 시도
        print("\n--- 소액(5,000원) 시장가 매수 테스트 시도 ---")
        # 5,000원 정수로 확실히 전달
        buy_res = client.buy_market_order(5000, "KRW-BTC")
        if buy_res:
            print(f"매수 테스트 성공: {buy_res}")
        else:
            print("매수 테스트 실패: 위 에러 로그를 확인하세요.")
        
    else:
        print("실패: 빗썸 API 인증에 실패했습니다.")
        print("1. API Key/Secret Key가 정확한지 확인하세요.")
        print("2. 빗썸 API 관리 페이지에서 '활성화' 상태인지 확인하세요.")
        print("3. 현재 서버의 공인 IP가 빗썸에 등록되어 있는지 확인하세요.")

if __name__ == "__main__":
    test()
