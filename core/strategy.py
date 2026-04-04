import pyupbit
import pandas as pd
from core.bithumb_client import BithumbClient
from config import SYMBOL, EXCHANGE

class ScalperStrategy:
    """
    RSI + Bollinger Band 'Buy the Dip' 전략.
    - 1차 매수: 볼린저 하단 이탈 + RSI ≤ rsi_threshold (잔고의 first_buy_ratio%)
    - 2차 매수: RSI ≤ rsi_threshold_2 + 현재가 < 평단 (잔고 전량)
    - 트레일링 익절: target_profit_rate 도달 후 trailing_stop_offset 하락 시 매도
    - 손절: stop_loss_rate 이하 시 즉시 매도
    """
    def __init__(self, ticker=SYMBOL):
        self.ticker = ticker
        self.exchange = EXCHANGE

    def _normalize_ticker(self, ticker, exchange):
        if exchange == "BITHUMB" and "-" in ticker:
            return ticker.split("-")[1]
        return ticker

    def get_ohlcv(self, exchange="UPBIT", interval="minute15", count=100):
        try:
            if exchange == "BITHUMB":
                interval_map = {
                    "minute1": "1m", "minute3": "3m", "minute5": "5m",
                    "minute10": "10m", "minute15": "15m", "minute30": "30m",
                    "minute60": "1h", "day": "24h"
                }
                bithumb_interval = interval_map.get(interval, "15m")
                return BithumbClient.get_ohlcv(self.ticker, interval=bithumb_interval, count=count)
            else:
                return pyupbit.get_ohlcv(self.ticker, interval=interval, count=count)
        except Exception:
            return None

    def get_rsi(self, exchange="UPBIT", interval="minute15", count=100):
        try:
            df = self.get_ohlcv(exchange, interval, count)
            if df is None or df.empty:
                return None

            delta = df['close'].diff()
            ups = delta.clip(lower=0)
            downs = (-delta).clip(lower=0)

            period = 14
            au = ups.rolling(window=period).mean()
            ad = downs.rolling(window=period).mean()

            rs = au / ad
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except Exception:
            return None

    def get_bollinger(self, exchange="UPBIT", interval="minute15", count=100, period=20, std_mult=2.0):
        """
        볼린저밴드 계산.
        Returns: (upper, middle, lower) or (None, None, None)
        """
        try:
            df = self.get_ohlcv(exchange, interval, count)
            if df is None or df.empty:
                return None, None, None

            close = df['close']
            middle = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            upper = middle + std_mult * std
            lower = middle - std_mult * std

            return upper.iloc[-1], middle.iloc[-1], lower.iloc[-1]
        except Exception:
            return None, None, None

    def is_below_bollinger_lower(self, exchange="UPBIT", interval="minute15"):
        """현재가가 볼린저 하단 이하인지 확인."""
        try:
            df = self.get_ohlcv(exchange, interval, 100)
            if df is None or df.empty:
                return False

            current_price = df['close'].iloc[-1]
            _, _, lower = self.get_bollinger(exchange, interval)
            if lower is None:
                return False

            return current_price <= lower
        except Exception:
            return False
