import pyupbit
import pandas as pd
from config import SYMBOL

class ScalperStrategy:
    """
    RSI-based 'Buy the Dip' & 1% Take-Profit Strategy.
    1. Buy when RSI < 30 (Oversold).
    2. Sell when price increases by 1% from entry price.
    3. Repeats 24/7.
    """
    def __init__(self, ticker=SYMBOL, buy_rsi_threshold=30, target_profit_rate=1.01, stop_loss_rate=0.98):
        self.ticker = ticker
        self.buy_rsi_threshold = buy_rsi_threshold
        self.target_profit_rate = target_profit_rate
        self.stop_loss_rate = stop_loss_rate

    def get_rsi(self, interval="minute15", count=100):
        """
        Calculates the Relative Strength Index (RSI) for the current ticker.
        """
        try:
            df = pyupbit.get_ohlcv(self.ticker, interval=interval, count=count)
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
