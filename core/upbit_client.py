import pyupbit
from config import UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY, SYMBOL

class UpbitClient:
    def __init__(self):
        self.upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
        self._is_authenticated = self._check_auth()

    def _check_auth(self):
        if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
            return False
        # Simple balance check for authentication
        try:
            self.upbit.get_balance("KRW")
            return True
        except Exception:
            return False

    def get_balances(self):
        """ Returns all balances in the account. """
        if not self._is_authenticated:
            return None
        return self.upbit.get_balances()

    def get_krw_balance(self):
        """ Returns the balance of KRW in the account. """
        if not self._is_authenticated:
            return 0.0
        return self.upbit.get_balance("KRW")

    def get_coin_balance(self, ticker=SYMBOL):
        """ Returns the balance of the specified coin. """
        if not self._is_authenticated:
            return 0.0
        return self.upbit.get_balance(ticker)

    def buy_market_order(self, amount, ticker=SYMBOL):
        """ Places a market buy order. """
        if not self._is_authenticated:
            return None
        return self.upbit.buy_market_order(ticker, amount)

    def sell_market_order(self, amount, ticker=SYMBOL):
        """ Places a market sell order. """
        if not self._is_authenticated:
            return None
        return self.upbit.sell_market_order(ticker, amount)

    @staticmethod
    def get_current_price(ticker=SYMBOL):
        """ Fetches the current price for a ticker. """
        return pyupbit.get_current_price(ticker)
