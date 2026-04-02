import pyupbit
import pybithumb
import pandas as pd
from config import SYMBOL, EXCHANGE

class ScalperStrategy:
    """
    RSI-based 'Buy the Dip' & 1% Take-Profit Strategy.
    Exchange-agnostic (Supports Upbit & Bithumb).
    """
    def __init__(self, ticker=SYMBOL, buy_rsi_threshold=30, target_profit_rate=1.01, stop_loss_rate=0.98):
        self.ticker = ticker
        self.exchange = EXCHANGE
        self.buy_rsi_threshold = buy_rsi_threshold
        self.target_profit_rate = target_profit_rate
        self.stop_loss_rate = stop_loss_rate

    def _get_api(self):
        return pyupbit if self.exchange == "UPBIT" else pybithumb

    def _normalize_ticker(self, ticker):
        if self.exchange == "BITHUMB" and "-" in ticker:
            return ticker.split("-")[1]
        return ticker

    def get_rsi(self, interval="minute15", count=100):
        """
        Calculates the Relative Strength Index (RSI) for the current ticker.
        """
        try:
            api = self._get_api()
            target = self._normalize_ticker(self.ticker)
            df = api.get_ohlcv(target, interval=interval, count=count)
            if df is None:
                return None
            
            delta = df['close'].diff()
            ups, downs = delta.copy(), delta.copy()
            ups[ups < 0] = 0
            downs[downs > 0] = 0

            period = 14
            au = ups.rolling(window=period).mean()
            ad = downs.abs().rolling(window=period).mean()
            
            rs = au / ad
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except Exception:
            return None

    def should_buy(self, current_rsi):
        """
        Returns True if RSI is below the threshold (Oversold condition).
        """
        if current_rsi is None:
            return False
        return current_rsi <= self.buy_rsi_threshold

    def should_sell(self, current_price, entry_price):
        """
        Returns True if the current price is at least 1% higher than the entry price.
        """
        if entry_price is None or entry_price == 0:
            return False
        
        profit_rate = current_price / entry_price
        return profit_rate >= self.target_profit_rate

    def should_stop_loss(self, current_price, entry_price):
        """
        Returns True if the current price is below the stop loss threshold (e.g., -2%).
        """
        if entry_price is None or entry_price == 0:
            return False
        
        profit_rate = current_price / entry_price
        return profit_rate <= self.stop_loss_rate

    def get_profit_status(self, current_price, entry_price):
        """
        Calculates current profit percentage and amount.
        """
        if not entry_price:
            return 0.0
        return ((current_price / entry_price) - 1) * 100
