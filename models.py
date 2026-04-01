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
    timestamp = Column(DateTime, default=datetime.datetime.now)

class BotSettings(Base):
    """
    Stores 봇의 상태 (On/Off) 및 실시간 설정값 저장.
    """
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True)
    is_running = Column(Boolean, default=False)
    avg_buy_price = Column(Float, default=0.0) # 매수 평단가 저장
    rsi_threshold = Column(Float, default=30.0) # 매수 진입 RSI 기준
    target_profit_rate = Column(Float, default=1.0) # 익절 기준 (%)
    stop_loss_rate = Column(Float, default=-2.0) # 손절 기준 (%)
    highest_profit_rate = Column(Float, default=0.0) # 매수 후 도달한 최고 수익률 (%)
    trailing_stop_offset = Column(Float, default=0.2) # 최고점 대비 하락 시 익절할 간격 (%)

# Database Setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
