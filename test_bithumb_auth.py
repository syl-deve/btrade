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
        
        # 잔고 확인
        krw_balance = client.get_krw_balance()
        print(f"현재 KRW 잔고: {krw_balance:,.0f}원")
        
        # 현재가 확인
        price = client.get_current_price("KRW-BTC")
        print(f"현재 BTC 가격: {price:,.0f}원")
        
    else:
        print("실패: 빗썸 API 인증에 실패했습니다.")
        print("1. API Key/Secret Key가 정확한지 확인하세요.")
        print("2. 빗썸 API 관리 페이지에서 '활성화' 상태인지 확인하세요.")
        print("3. 현재 서버의 공인 IP가 빗썸에 등록되어 있는지 확인하세요.")

if __name__ == "__main__":
    test()
