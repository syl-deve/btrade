import pandas as pd
from core.bithumb_client import BithumbClient
from config import SYMBOL

class ScalperStrategy:
    """
    RSI + Bollinger Band + MACD + Volume + ATR 복합 전략.
    - 1차 매수: 볼린저 하단 + RSI <= rsi_threshold + MACD 반전 + 거래량 급증
    - 2차 매수: RSI <= rsi_threshold_2 + 현재가 < 평단
    - 트레일링 익절 / ATR 동적 손절
    """
    def __init__(self, ticker=SYMBOL):
        self.ticker = ticker

    def _normalize_ticker(self, ticker):
        if "-" in ticker:
            return ticker.split("-")[1]
        return ticker

    def get_ohlcv(self, exchange="BITHUMB", interval="minute15", count=120):
        try:
            interval_map = {
                "minute1": "1m", "minute3": "3m", "minute5": "5m",
                "minute10": "10m", "minute15": "15m", "minute30": "30m",
                "minute60": "1h", "day": "24h"
            }
            bithumb_interval = interval_map.get(interval, "15m")
            return BithumbClient.get_ohlcv(self.ticker, interval=bithumb_interval, count=count)
        except Exception:
            return None

    def get_rsi(self, exchange="BITHUMB", interval="minute15", count=120):
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
            rs = au / ad.replace(0, 1e-10)  # div-by-zero 방지
            rsi = 100 - (100 / (1 + rs))
            val = rsi.iloc[-1]
            if val != val:  # nan 체크
                return None
            return val
        except Exception:
            return None

    def get_bollinger(self, exchange="BITHUMB", interval="minute15", count=120, period=20, std_mult=2.0):
        """Returns (upper, middle, lower) or (None, None, None)."""
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

    def is_below_bollinger_lower(self, exchange="BITHUMB", interval="minute15"):
        """현재가가 볼린저 하단 이하인지 확인."""
        try:
            df = self.get_ohlcv(exchange, interval, 120)
            if df is None or df.empty:
                return False
            current_price = df['close'].iloc[-1]
            _, _, lower = self.get_bollinger(exchange, interval)
            if lower is None:
                return False
            return current_price <= lower
        except Exception:
            return False

    def get_macd(self, exchange="BITHUMB", interval="minute15", count=120):
        """
        MACD 계산 (12/26/9).
        Returns: (macd, signal, histogram) 최근 3봉 리스트 or (None, None, None)
        """
        try:
            df = self.get_ohlcv(exchange, interval, count)
            if df is None or df.empty:
                return None, None, None

            close = df['close']
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            return macd.iloc[-1], signal.iloc[-1], histogram.iloc[-3:].tolist()
        except Exception:
            return None, None, None

    def is_macd_reversing(self, exchange="BITHUMB", interval="minute15"):
        """
        MACD 히스토그램 바닥 반전 감지.
        - 히스토그램이 음수 구간에서 이전 봉보다 커지는 시점
        """
        try:
            _, _, hist = self.get_macd(exchange, interval)
            if hist is None or len(hist) < 3:
                return False
            h0, h1, h2 = hist[0], hist[1], hist[2]
            return h2 < 0 and h2 > h1
        except Exception:
            return False

    def is_volume_surging(self, exchange="BITHUMB", interval="minute15", multiplier=1.5, period=20):
        """현재봉 거래량이 최근 period봉 평균의 multiplier배 이상인지 확인."""
        try:
            df = self.get_ohlcv(exchange, interval, period + 5)
            if df is None or df.empty or 'volume' not in df.columns:
                return False
            avg_volume = df['volume'].iloc[:-1].rolling(window=period).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            if avg_volume is None or avg_volume == 0:
                return False
            return current_volume >= avg_volume * multiplier
        except Exception:
            return False

    def get_volume_ratio(self, exchange="BITHUMB", interval="minute15", period=20):
        """현재봉 거래량 / 20봉 평균 비율 반환. Returns (current_volume, avg_volume, ratio) or (None, None, None)."""
        try:
            df = self.get_ohlcv(exchange, interval, period + 5)
            if df is None or df.empty or 'volume' not in df.columns:
                return None, None, None
            avg_volume = df['volume'].iloc[:-1].rolling(window=period).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            if avg_volume is None or avg_volume == 0:
                return None, None, None
            return float(current_volume), float(avg_volume), float(current_volume / avg_volume)
        except Exception:
            return None, None, None

    def get_atr(self, exchange="BITHUMB", interval="minute15", period=14, count=120):
        """ATR(Average True Range) 계산. Returns ATR값 or None."""
        try:
            df = self.get_ohlcv(exchange, interval, count)
            if df is None or df.empty:
                return None

            high = df['high']
            low = df['low']
            close = df['close']

            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            return atr.iloc[-1]
        except Exception:
            return None

    def get_dynamic_stop_loss(self, exchange="BITHUMB", current_price=None, atr_multiplier=1.5, interval="minute15"):
        """
        ATR 기반 동적 손절율 계산.
        Returns: 손절율 (음수 %, 예: -1.5)
        """
        try:
            atr = self.get_atr(exchange, interval)
            if atr is None or current_price is None or current_price == 0:
                return None
            atr_pct = (atr / current_price) * 100
            stop_pct = -(atr_pct * atr_multiplier)
            return max(-3.0, min(-0.5, stop_pct))
        except Exception:
            return None

    def get_ema(self, exchange="BITHUMB", interval="minute15", period=20, count=120):
        try:
            df = self.get_ohlcv(exchange, interval, max(count, period + 5))
            if df is None or df.empty:
                return None
            ema = df["close"].ewm(span=period, adjust=False).mean()
            return float(ema.iloc[-1])
        except Exception:
            return None

    def get_chandelier_stop(self, exchange="BITHUMB", interval="minute15", period=14, atr_multiplier=2.5, count=120):
        try:
            df = self.get_ohlcv(exchange, interval, max(count, period + 5))
            if df is None or df.empty:
                return None
            atr = self.get_atr(exchange, interval, period, count)
            if atr is None:
                return None
            highest_high = float(df["high"].tail(period).max())
            return highest_high - (float(atr) * atr_multiplier)
        except Exception:
            return None

    def get_trend_exit_state(
        self,
        exchange="BITHUMB",
        current_price=None,
        interval="minute15",
        ema_period=20,
        chandelier_atr_multiplier=2.5,
        macd_weak_confirm_candles=2,
    ):
        try:
            if current_price is None:
                return {
                    "trend_ok": False,
                    "ema": None,
                    "chandelier_stop": None,
                    "macd_weak": None,
                }

            ema = self.get_ema(exchange, interval, ema_period)
            chandelier_stop = self.get_chandelier_stop(
                exchange,
                interval,
                period=14,
                atr_multiplier=chandelier_atr_multiplier,
            )
            _, _, hist = self.get_macd(exchange, interval)

            macd_weak = None
            if hist and len(hist) >= max(2, macd_weak_confirm_candles + 1):
                recent = hist[-(macd_weak_confirm_candles + 1):]
                macd_weak = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))

            above_ema = ema is not None and current_price >= ema
            above_chandelier = chandelier_stop is not None and current_price > chandelier_stop
            macd_ok = macd_weak is False or macd_weak is None

            return {
                "trend_ok": bool(above_ema and above_chandelier and macd_ok),
                "ema": ema,
                "chandelier_stop": chandelier_stop,
                "macd_weak": macd_weak,
            }
        except Exception:
            return {
                "trend_ok": False,
                "ema": None,
                "chandelier_stop": None,
                "macd_weak": None,
            }
