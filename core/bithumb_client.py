import jwt
import uuid
import hashlib
import time
import requests
import logging
import base64
import json
from urllib.parse import urlencode, quote
from config import BITHUMB_ACCESS_KEY, BITHUMB_SECRET_KEY, SYMBOL

logger = logging.getLogger(__name__)

class BithumbClient:
    def __init__(self):
        self.api_url = "https://api.bithumb.com"
        self.access_key = BITHUMB_ACCESS_KEY
        self.secret_key = BITHUMB_SECRET_KEY
        self._is_authenticated = self._check_auth()

    def _get_headers(self, params=None):
        """ Generates JWT Authorization header for Bithumb v1 API """
        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000)
        }
        
        if params:
            # Sort parameters alphabetically to ensure consistent query string
            sorted_params = dict(sorted(params.items()))
            query_string = urlencode(sorted_params, quote_via=quote)
            
            # Generate SHA512 hash of the query string
            m = hashlib.sha512()
            m.update(query_string.encode())
            query_hash = m.hexdigest()
            
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'

        # Use secret key as is for signing
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _normalize_ticker(self, ticker):
        """ Ensure ticker is in KRW-BTC format for v1 API (same as Upbit) """
        if "-" not in ticker:
            return f"KRW-{ticker}"
        return ticker

    def _check_auth(self):
        """ Verifies API Key by fetching accounts """
        if not self.access_key or not self.secret_key:
            return False
        try:
            headers = self._get_headers()
            res = requests.get(f"{self.api_url}/v1/accounts", headers=headers)
            if res.status_code == 200:
                return True
            else:
                logger.error(f"Bithumb V1 Auth Failed: {res.json()} (Status: {res.status_code})")
                return False
        except Exception as e:
            logger.error(f"Bithumb V1 Auth Check Exception: {e}")
            return False

    def get_krw_balance(self):
        """ Returns the KRW balance from /v1/accounts """
        if not self._is_authenticated:
            return 0.0
        try:
            headers = self._get_headers()
            res = requests.get(f"{self.api_url}/v1/accounts", headers=headers)
            if res.status_code == 200:
                accounts = res.json()
                for acc in accounts:
                    if acc['currency'] == 'KRW':
                        return float(acc['balance'])
            return 0.0
        except Exception as e:
            logger.error(f"Bithumb KRW Balance Error: {e}")
            return 0.0

    def get_coin_balance(self, ticker=SYMBOL):
        """ Returns the coin balance from /v1/accounts """
        if not self._is_authenticated:
            return 0.0
        try:
            target_coin = ticker.split("-")[1] if "-" in ticker else ticker
            headers = self._get_headers()
            res = requests.get(f"{self.api_url}/v1/accounts", headers=headers)
            if res.status_code == 200:
                accounts = res.json()
                for acc in accounts:
                    if acc['currency'] == target_coin:
                        return float(acc['balance'])
            return 0.0
        except Exception as e:
            logger.error(f"Bithumb {ticker} Balance Error: {e}")
            return 0.0

    @staticmethod
    def get_current_price(ticker=SYMBOL):
        """ Fetches current price via Public v1 API (No Auth needed) """
        try:
            # v1 Public API uses 'markets' param
            api_url = "https://api.bithumb.com/v1/ticker"
            params = {"markets": ticker}
            res = requests.get(api_url, params=params)
            if res.status_code == 200:
                data = res.json()
                if data:
                    return float(data[0]['trade_price'])
            return None
        except Exception as e:
            logger.error(f"Bithumb Get Current Price Error: {e}")
            return None

    def buy_market_order(self, krw_amount, ticker=SYMBOL):
        """ Market Buy via /v1/orders """
        if not self._is_authenticated:
            return None
        try:
            ticker = self._normalize_ticker(ticker)
            # Sort keys to ensure hash consistency
            params = dict(sorted(params.items()))
            
            # Generate JSON body with NO spaces (important for hash match)
            json_body = json.dumps(params, separators=(',', ':'))
            
            headers = self._get_headers(params)
            res = requests.post(f"{self.api_url}/v1/orders", data=json_body, headers=headers)
            
            data = res.json()
            if res.status_code != 201:
                logger.error(f"Bithumb Market Buy Failed: {data} (Status: {res.status_code})")
                return None
            return data
        except Exception as e:
            logger.error(f"Bithumb Market Buy Error: {e}")
            return None

    def sell_market_order(self, amount, ticker=SYMBOL):
        """ Market Sell via /v1/orders """
        if not self._is_authenticated:
            return None
        try:
            ticker = self._normalize_ticker(ticker)
            # Sort keys to ensure hash consistency
            params = dict(sorted(params.items()))
            
            # Generate JSON body with NO spaces (important for hash match)
            json_body = json.dumps(params, separators=(',', ':'))
            
            headers = self._get_headers(params)
            res = requests.post(f"{self.api_url}/v1/orders", data=json_body, headers=headers)
            
            data = res.json()
            if res.status_code != 201:
                logger.error(f"Bithumb Market Sell Failed: {data} (Status: {res.status_code})")
                return None
            return data
        except Exception as e:
            logger.error(f"Bithumb Market Sell Error: {e}")
            return None
