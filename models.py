from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from config import DATABASE_URL

Base = declarative_base()

class TradeHistory(Base):
    __tablename__ = "trade_history"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    side = Column(String)  # BUY or SELL
    price = Column(Float)
    volume = Column(Float)
    total_amount = Column(Float)
    net_profit = Column(Float, default=0.0) # 매도 시 확정된 수익금 (매도금 - 매수원금)
    fee = Column(Float, nullable=True)       # 거래 수수료 (원화)
    timestamp = Column(DateTime, default=datetime.datetime.now)

class BotSettings(Base):
    """
    Stores 봇의 상태 (On/Off) 및 실시간 설정값 저장.
    """
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True)
    is_running = Column(Boolean, default=False)
    avg_buy_price = Column(Float, default=0.0)
    rsi_threshold = Column(Float, default=35.0)      # 1차 매수 RSI 기준
    rsi_threshold_2 = Column(Float, default=28.0)    # 2차 매수 RSI 기준 (추가매수)
    target_profit_rate = Column(Float, default=1.5)  # 익절 기준 (%)
    stop_loss_rate = Column(Float, default=-1.0)     # 손절 기준 (%)
    highest_profit_rate = Column(Float, default=0.0)
    trailing_stop_offset = Column(Float, default=0.3) # 트레일링 오프셋 (%)
    exchange = Column(String, default="BITHUMB")
    buy_count = Column(Integer, default=0)
    use_bollinger = Column(Boolean, default=True)
    first_buy_ratio = Column(Float, default=0.6)
    # A. 매수 타이밍 필터
    use_macd = Column(Boolean, default=True)         # MACD 히스토그램 반전 필터
    use_volume_filter = Column(Boolean, default=True) # 거래량 급증 필터
    volume_multiplier = Column(Float, default=1.5)   # 평균 거래량 대비 배수
    # B. 동적 손익 조정
    atr_multiplier = Column(Float, default=1.5)      # ATR 기반 손절폭 배수
    use_atr = Column(Boolean, default=True)          # ATR 동적 손절 사용 여부
    max_hold_hours = Column(Float, default=4.0)      # 최대 보유 시간 (시간)
    position_opened_at = Column(DateTime, nullable=True)  # 포지션 진입 시각
    # C. 리스크 관리
    daily_loss_limit = Column(Float, default=-50000.0)    # 일일 최대 손실 (원)
    use_daily_loss = Column(Boolean, default=True)        # 일일 손실 한도 사용 여부
    max_consecutive_loss = Column(Integer, default=3)     # 연속 손절 허용 횟수
    cooldown_minutes = Column(Integer, default=60)        # 쿨다운 시간 (분)
    cooldown_until = Column(DateTime, nullable=True)      # 쿨다운 종료 시각

# Database Setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
