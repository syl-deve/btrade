import sys
import os
from config import EXCHANGE, BITHUMB_ACCESS_KEY, BITHUMB_SECRET_KEY
from core.bithumb_client import BithumbClient

def test():
    print(f"현재 설정된 거래소: {EXCHANGE}")
    
    if EXCHANGE != "BITHUMB":
        print("주의: EXCHANGE가 BITHUMB으로 설정되어 있지 않습니다.")
    
    if not BITHUMB_ACCESS_KEY or not BITHUMB_SECRET_KEY:
        print("에러: 빗썸 API 키가 .env 파일에 설정되어 있지 않습니다.")
        return

    client = BithumbClient()
    if client._is_authenticated:
        print("성공: 빗썸 API 인증에 성공했습니다!")
        # 디버깅을 위해 생으로 호출해봅니다.
        raw_balance = client.bithumb.get_balance("BTC")
        print(f"DEBUG - raw_balance 타입: {type(raw_balance)}")
        print(f"DEBUG - raw_balance 내용: {raw_balance}")
        
        try:
            balance = client.get_krw_balance()
            print(f"현재 KRW 잔고: {balance:,.0f}원")
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {e}")
    else:
        print("실패: 빗썸 API 인증에 실패했습니다. 키 또는 IP 설정을 확인해 주세요.")

if __name__ == "__main__":
    test()
