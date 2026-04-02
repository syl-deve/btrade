import pybithumb
import logging
from config import BITHUMB_ACCESS_KEY, BITHUMB_SECRET_KEY, SYMBOL

logger = logging.getLogger(__name__)

class BithumbClient:
    def __init__(self):
        # pybithumb Bithumb class expects (conkey, seckey)
        self.bithumb = pybithumb.Bithumb(BITHUMB_ACCESS_KEY, BITHUMB_SECRET_KEY)
        self._is_authenticated = self._check_auth()

    def _normalize_ticker(self, ticker):
        """ Converts KRW-BTC to BTC for Bithumb """
        if "-" in ticker:
            return ticker.split("-")[1]
        return ticker

    def _check_auth(self):
        if not BITHUMB_ACCESS_KEY or not BITHUMB_SECRET_KEY:
            return False
        try:
            # Simple balance check
            res = self.bithumb.get_balance("BTC")
            if isinstance(res, dict) and res.get('status') != '0000':
                logger.error(f"Bithumb Auth Failed: {res.get('message')} (Status: {res.get('status')})")
                return False
            # Standard return is a tuple of length 4
            return isinstance(res, (list, tuple)) and len(res) == 4
        except Exception as e:
            logger.error(f"Bithumb Auth Check Exception: {e}")
            return False

    def get_krw_balance(self):
        """ Returns the KRW balance. """
        if not self._is_authenticated:
            return 0.0
        try:
            res = self.bithumb.get_balance("BTC")
            if isinstance(res, (list, tuple)) and len(res) == 4:
                # get_balance returns (total_coin, used_coin, total_krw, used_krw)
                _, _, total_krw, _ = res
                return float(total_krw)
            else:
                logger.error(f"Bithumb Get KRW Balance Unexpected Response: {res}")
                return 0.0
        except Exception as e:
            logger.error(f"Bithumb KRW Balance Error: {e}")
            return 0.0

    def get_coin_balance(self, ticker=SYMBOL):
        """ Returns the coin balance. """
        if not self._is_authenticated:
            return 0.0
        try:
            target = self._normalize_ticker(ticker)
            res = self.bithumb.get_balance(target)
            if isinstance(res, (list, tuple)) and len(res) == 4:
                # get_balance returns (total_coin, used_coin, ...)
                total_coin, _, _, _ = res
                return float(total_coin)
            else:
                logger.error(f"Bithumb Get {ticker} Balance Unexpected Response: {res}")
                return 0.0
        except Exception as e:
            logger.error(f"Bithumb {ticker} Balance Error: {e}")
            return 0.0

    @staticmethod
    def get_current_price(ticker=SYMBOL):
        """ Fetches the current price. """
        try:
            # pybithumb needs just BTC
            if "-" in ticker:
                ticker = ticker.split("-")[1]
            return float(pybithumb.get_current_price(ticker))
        except Exception:
            return None

    def buy_market_order(self, krw_amount, ticker=SYMBOL):
        """ Market buy. Note: pybithumb market buy takes 'units' usually? 
            Wait, pybithumb.buy_market_order takes (ticker, units). 
            Normally market buys take KRW amount. Let's check pybithumb docs.
            Actually, pybithumb's buy_market_order takes ticker and quantity.
        """
        if not self._is_authenticated:
            return None
        target = self._normalize_ticker(ticker)
        # We need to calculate units based on current price if we want to buy by KRW amount
        price = self.get_current_price(target)
        if not price: return None
        units = (krw_amount * 0.999) / price # subtract fee approx
        return self.bithumb.buy_market_order(target, units)

    def sell_market_order(self, amount, ticker=SYMBOL):
        """ Market sell. """
        if not self._is_authenticated:
            return None
        target = self._normalize_ticker(ticker)
        return self.bithumb.sell_market_order(target, amount)
