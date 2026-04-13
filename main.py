import asyncio
import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn

from config import SYMBOL, DASHBOARD_PASSWORD, TRADING_INTERVAL_MINUTES, EXCHANGE
from models import SessionLocal, init_db, BotSettings, TradeHistory
from core.bithumb_client import BithumbClient
from core.strategy import ScalperStrategy
from core.discord_notifier import send_discord_message
from contextlib import asynccontextmanager
import logging
import sys
import traceback

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import secrets
import time
from pydantic import BaseModel, Field
from typing import Optional

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Security Config ---
BITHUMB_FEE_RATE = 0.0004 # 빗썸 0.04% (수수료 쿠폰 적용)

# 세션 및 CSRF를 위한 보안 키 (실제 상용 시 .env로 관리 권장)
SESSION_SECRET_KEY = hashlib.sha256(DASHBOARD_PASSWORD.encode()).hexdigest()
CSRF_SECRET = secrets.token_hex(32)

# --- Rate Limiting Config ---
LOGIN_ATTEMPTS = {}  # {ip: {"count": n, "blocked_until": timestamp}}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 600 # 10 minutes in seconds

class SettingsUpdate(BaseModel):
    rsi_threshold: float = Field(default=35.0, ge=10, le=90)
    rsi_threshold_2: float = Field(default=28.0, ge=10, le=90)
    target_profit_rate: float = Field(default=1.5, ge=0.1, le=100.0)
    stop_loss_rate: float = Field(default=-1.0, ge=-50.0, le=-0.1)
    trailing_offset: float = Field(default=0.3, ge=0.01, le=10.0)
    exchange: str = Field(default="BITHUMB")
    use_bollinger: bool = True
    first_buy_ratio: float = Field(default=0.6, ge=0.1, le=1.0)
    use_macd: bool = True
    use_volume_filter: bool = True
    volume_multiplier: float = Field(default=1.5, ge=1.0, le=10.0)
    atr_multiplier: float = Field(default=1.5, ge=0.5, le=5.0)
    daily_loss_limit: float = Field(default=-50000.0, le=0.0)
    max_consecutive_loss: int = Field(default=3, ge=1, le=10)
    cooldown_minutes: int = Field(default=60, ge=1, le=1440)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self';"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

def get_fee_rate():
    return BITHUMB_FEE_RATE

# --- DB 즉시 마이그레이션 (모듈 로드 시 실행) ---
def _run_db_migrations():
    import sqlite3 as _sq, os as _os
    from config import DATABASE_URL as _url
    path = _url.replace("sqlite:///", "")
    if path.startswith("./"):
        path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), path[2:])
    conn = _sq.connect(path)
    # trade_history.fee 컬럼
    try:
        conn.execute("ALTER TABLE trade_history ADD COLUMN fee FLOAT")
    except Exception:
        pass
    # fee 전체 재계산 (요율 변경 시 반영, 빗썸 0.04% 쿠폰 적용)
    # BUY: 매수금액 × 0.04% (단건 수수료)
    # SELL: 매도금액 × 0.04% (단건 수수료, 빗썸 앱 기준 — net_profit에는 매수+매도 양쪽 합산 반영)
    conn.execute("UPDATE trade_history SET fee = total_amount * 0.0004 WHERE side = 'BUY'")
    conn.execute("UPDATE trade_history SET fee = total_amount * 0.0004 WHERE side = 'SELL'")
    conn.commit()
    conn.close()
    logging.getLogger(__name__).info("[Migration] fee 소급 적용 완료 (BUY×0.04%, SELL×0.04%)")

_run_db_migrations()

# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB (will create columns in fresh DB)
    init_db()
    
    # Ensure BotSettings exist
    db = SessionLocal()
    from sqlalchemy import text

    # --- Auto Migration ---
    migrations = [
        ("exchange",               "ALTER TABLE bot_settings ADD COLUMN exchange VARCHAR DEFAULT 'BITHUMB'"),
        ("rsi_threshold_2",        "ALTER TABLE bot_settings ADD COLUMN rsi_threshold_2 FLOAT DEFAULT 28.0"),
        ("buy_count",              "ALTER TABLE bot_settings ADD COLUMN buy_count INTEGER DEFAULT 0"),
        ("use_bollinger",          "ALTER TABLE bot_settings ADD COLUMN use_bollinger BOOLEAN DEFAULT 1"),
        ("first_buy_ratio",        "ALTER TABLE bot_settings ADD COLUMN first_buy_ratio FLOAT DEFAULT 0.6"),
        ("use_macd",               "ALTER TABLE bot_settings ADD COLUMN use_macd BOOLEAN DEFAULT 1"),
        ("use_volume_filter",      "ALTER TABLE bot_settings ADD COLUMN use_volume_filter BOOLEAN DEFAULT 1"),
        ("volume_multiplier",      "ALTER TABLE bot_settings ADD COLUMN volume_multiplier FLOAT DEFAULT 1.5"),
        ("atr_multiplier",         "ALTER TABLE bot_settings ADD COLUMN atr_multiplier FLOAT DEFAULT 1.5"),
        ("max_hold_hours",         "ALTER TABLE bot_settings ADD COLUMN max_hold_hours FLOAT DEFAULT 4.0"),
        ("position_opened_at",     "ALTER TABLE bot_settings ADD COLUMN position_opened_at DATETIME"),
        ("daily_loss_limit",       "ALTER TABLE bot_settings ADD COLUMN daily_loss_limit FLOAT DEFAULT -50000.0"),
        ("max_consecutive_loss",   "ALTER TABLE bot_settings ADD COLUMN max_consecutive_loss INTEGER DEFAULT 3"),
        ("cooldown_minutes",       "ALTER TABLE bot_settings ADD COLUMN cooldown_minutes INTEGER DEFAULT 60"),
        ("cooldown_until",         "ALTER TABLE bot_settings ADD COLUMN cooldown_until DATETIME"),
    ]
    for col, sql in migrations:
        try:
            db.execute(text(f"SELECT {col} FROM bot_settings LIMIT 1"))
        except Exception:
            logger.info(f"[Migration] Adding '{col}' column...")
            try:
                db.execute(text(sql))
                db.commit()
            except Exception as e:
                logger.error(f"[Migration Error] {col}: {e}")
    # ---------------------

    if not db.query(BotSettings).first():
        db.add(BotSettings(
            is_running=False,
            avg_buy_price=0.0,
            rsi_threshold=35.0,
            rsi_threshold_2=28.0,
            target_profit_rate=1.5,
            stop_loss_rate=-1.0,
            highest_profit_rate=0.0,
            trailing_stop_offset=0.3,
            buy_count=0,
            use_bollinger=True,
            first_buy_ratio=0.6,
            use_macd=True,
            use_volume_filter=True,
            volume_multiplier=1.5,
            atr_multiplier=1.5,
            max_hold_hours=4.0,
            daily_loss_limit=-50000.0,
            max_consecutive_loss=3,
            cooldown_minutes=60,
        ))
        db.commit()
    db.close()
    
    # Start the trading loop in the background
    task = asyncio.create_task(trading_loop())
    yield
    # Clean up (optional)
    task.cancel()

# FastAPI Setup
app = FastAPI(title="BITRADE Dashboard", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global Client and Strategy Instances
bithumb_client = None
strategy = None

def init_clients():
    global bithumb_client, strategy
    try:
        bithumb_client = BithumbClient()
        strategy = ScalperStrategy()
    except Exception:
        import traceback
        print("--- ERROR DURING CLIENT INITIALIZATION ---")
        traceback.print_exc()

init_clients()

def get_client(exchange="BITHUMB"):
    global bithumb_client
    if exchange == "BITHUMB":
        # Always check if client needs re-initialization if not authorized
        if not bithumb_client or not getattr(bithumb_client, "_is_authenticated", False):
            try:
                bithumb_client = BithumbClient()
            except Exception:
                pass
        return bithumb_client
    return bithumb_client

def is_client_authorized(exchange="BITHUMB"):
    client = get_client(exchange)
    if not client: return False
    # BithumbClient has _is_authenticated attribute
    return getattr(client, "_is_authenticated", False)

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Background Trading Task ---
def _reset_position(bot_settings):
    bot_settings.avg_buy_price = 0.0
    bot_settings.highest_profit_rate = 0.0
    bot_settings.buy_count = 0
    bot_settings.position_opened_at = None

def _record_sell(db, current_price, coin_balance, bot_settings):
    fee_rate = get_fee_rate()
    buy_principle = bot_settings.avg_buy_price * coin_balance
    sell_total = current_price * coin_balance
    buy_fee = buy_principle * fee_rate
    sell_fee = sell_total * fee_rate
    total_fee = buy_fee + sell_fee
    net_profit = sell_total - buy_principle - total_fee
    db.add(TradeHistory(
        symbol=SYMBOL, side="SELL", price=current_price,
        volume=coin_balance, total_amount=sell_total,
        net_profit=net_profit, fee=sell_fee  # 매도 단건 수수료만 표시 (빗썸 앱 기준)
    ))
    _reset_position(bot_settings)
    db.commit()
    return net_profit

def _record_buy(db, current_price, buy_amount):
    fee_rate = get_fee_rate()
    fee = buy_amount * fee_rate
    db.add(TradeHistory(
        symbol=SYMBOL, side="BUY", price=current_price,
        volume=buy_amount / current_price, total_amount=buy_amount, fee=fee
    ))
    db.commit()

def _check_daily_loss(db, bot_settings):
    """당일 실현 손실이 한도 초과 시 봇 정지. True 반환 시 정지됨."""
    import datetime as dt
    # KST(UTC+9) 기준 오늘 자정
    kst_now = dt.datetime.utcnow() + dt.timedelta(hours=9)
    kst_today_start = dt.datetime.combine(kst_now.date(), dt.time.min)
    today_start = kst_today_start - dt.timedelta(hours=9)  # UTC로 변환
    today_sells = db.query(TradeHistory).filter(
        TradeHistory.side == "SELL",
        TradeHistory.timestamp >= today_start,
        TradeHistory.net_profit < 0
    ).all()
    today_loss = sum(t.net_profit for t in today_sells if t.net_profit is not None)
    limit = bot_settings.daily_loss_limit or -50000.0
    if today_loss <= limit:
        bot_settings.is_running = False
        db.commit()
        logger.warning(f"🛑 일일 손실 한도 초과: {today_loss:,.0f} KRW ≤ {limit:,.0f} KRW → 봇 자동 정지")
        send_discord_message("🛑 일일 손실 한도 초과", f"오늘 손실: {today_loss:,.0f} KRW\n한도: {limit:,.0f} KRW\n봇 자동 정지됨", color=0xff0000)
        return True
    return False

def _check_consecutive_loss(db, bot_settings):
    """연속 손절 횟수 초과 시 쿨다운 설정. True 반환 시 쿨다운 중."""
    import datetime as dt
    now = dt.datetime.now()
    # 이미 쿨다운 중
    if bot_settings.cooldown_until and now < bot_settings.cooldown_until:
        remaining = int((bot_settings.cooldown_until - now).total_seconds() / 60)
        logger.info(f"[쿨다운] 매수 금지 중 — {remaining}분 남음")
        return True

    max_loss = bot_settings.max_consecutive_loss or 3
    recent_sells = db.query(TradeHistory).filter(
        TradeHistory.side == "SELL"
    ).order_by(TradeHistory.timestamp.desc()).limit(max_loss).all()

    if len(recent_sells) >= max_loss and all(t.net_profit < 0 for t in recent_sells):
        cooldown_min = bot_settings.cooldown_minutes or 60
        bot_settings.cooldown_until = now + dt.timedelta(minutes=cooldown_min)
        db.commit()
        logger.warning(f"⏸️ {max_loss}연속 손절 감지 → {cooldown_min}분 쿨다운 시작")
        send_discord_message("⏸️ 연속 손절 쿨다운", f"{max_loss}회 연속 손절\n{cooldown_min}분간 매수 금지", color=0xffa500)
        return True
    return False

async def trading_loop():
    logger.info("[Trading] Starting background loop...")
    while True:
        try:
            db = SessionLocal()
            try:
                import datetime as dt
                bot_settings = db.query(BotSettings).first()
                if not bot_settings:
                    bot_settings = BotSettings(is_running=False)
                    db.add(bot_settings)
                    db.commit()
                    db.refresh(bot_settings)

                if not bot_settings.is_running:
                    await asyncio.sleep(5)
                    continue

                target_exchange = bot_settings.exchange or "BITHUMB"
                current_client = get_client(target_exchange)

                if not is_client_authorized(target_exchange):
                    logger.warning(f"🚨 API Key for {target_exchange} NOT AUTHENTICATED.")
                    await asyncio.sleep(60)
                    continue

                current_price = current_client.get_current_price(SYMBOL)
                current_rsi = strategy.get_rsi(target_exchange)
                coin_balance = current_client.get_coin_balance(SYMBOL)

                if current_price is None or coin_balance is None:
                    await asyncio.sleep(10)
                    continue


                rsi_display = f"{current_rsi:.2f}" if current_rsi else "N/A"
                logger.info(f"[Loop] {SYMBOL} @ {current_price:,.0f} | RSI: {rsi_display} | Held: {coin_balance:.6f} | Buys: {bot_settings.buy_count}")

                # ── 보유 중 ──────────────────────────────────────────
                if coin_balance > 0.0001 and bot_settings.avg_buy_price > 0:
                    profit_rate = ((current_price / bot_settings.avg_buy_price) - 1) * 100

                    # B. ATR 동적 손절율 계산
                    dynamic_sl = strategy.get_dynamic_stop_loss(
                        target_exchange, current_price, bot_settings.atr_multiplier or 1.5
                    )
                    effective_sl = dynamic_sl if dynamic_sl is not None else bot_settings.stop_loss_rate

                    # 1. 긴급 손절 (ATR 동적 손절 적용)
                    if profit_rate <= effective_sl:
                        res = current_client.sell_market_order(coin_balance)
                        if res:
                            net_profit = _record_sell(db, current_price, coin_balance, bot_settings)
                            logger.warning(f"🚨 ATR 손절: SOLD @ {current_price:,.0f} ({profit_rate:.2f}%, SL: {effective_sl:.2f}%) | P&L: {net_profit:,.0f} KRW")
                            send_discord_message("🚨 ATR 손절", f"손절율: {effective_sl:.2f}% (ATR 동적)\n체결가: {current_price:,.0f}\n손실: {net_profit:,.0f} KRW", color=0x0000ff)
                            _check_daily_loss(db, bot_settings)
                            _check_consecutive_loss(db, bot_settings)

                    else:
                        # 2. 2차 추가매수
                        if bot_settings.buy_count == 1 and current_rsi and current_rsi <= bot_settings.rsi_threshold_2 and current_price < bot_settings.avg_buy_price:
                            krw_balance = current_client.get_krw_balance()
                            if krw_balance > 5000:
                                buy_amount = krw_balance * 0.995
                                res = current_client.buy_market_order(buy_amount)
                                if res:
                                    new_coin = buy_amount / current_price
                                    total_coin = coin_balance + new_coin
                                    # 1차 실제 투자금을 DB에서 조회해 정확한 평단 계산
                                    first_buy = db.query(TradeHistory).filter(
                                        TradeHistory.side == "BUY"
                                    ).order_by(TradeHistory.timestamp.desc()).first()
                                    first_cost = first_buy.total_amount if first_buy else bot_settings.avg_buy_price * coin_balance
                                    total_cost = first_cost + buy_amount
                                    bot_settings.avg_buy_price = total_cost / total_coin
                                    bot_settings.buy_count = 2
                                    bot_settings.highest_profit_rate = 0.0
                                    _record_buy(db, current_price, buy_amount)
                                    db.commit()
                                    logger.info(f"💎 2차 매수: {current_price:,.0f} | RSI: {current_rsi:.2f} | 새 평단: {bot_settings.avg_buy_price:,.0f}")
                                    send_discord_message("💎 2차 추가매수", f"RSI {current_rsi:.2f} → 추가매수\n체결가: {current_price:,.0f}\n새 평단: {bot_settings.avg_buy_price:,.0f}", color=0x8b5cf6)

                        # 3. 트레일링 익절
                        if profit_rate > bot_settings.highest_profit_rate:
                            bot_settings.highest_profit_rate = profit_rate
                            db.commit()

                        if bot_settings.highest_profit_rate >= bot_settings.target_profit_rate:
                            if profit_rate <= (bot_settings.highest_profit_rate - bot_settings.trailing_stop_offset):
                                res = current_client.sell_market_order(coin_balance)
                                if res:
                                    net_profit = _record_sell(db, current_price, coin_balance, bot_settings)
                                    logger.info(f"🎣 트레일링 익절: SOLD @ {current_price:,.0f} (고점: {bot_settings.highest_profit_rate:.2f}% → {profit_rate:.2f}%) | P&L: +{net_profit:,.0f} KRW")
                                    send_discord_message("🎣 트레일링 익절", f"고점 {bot_settings.highest_profit_rate:.2f}% → {profit_rate:.2f}%\n체결가: {current_price:,.0f}\n수익: +{net_profit:,.0f} KRW", color=0x00ff00)
                                    _check_daily_loss(db, bot_settings)
                        else:
                            logger.info(f"[홀딩] 수익률: {profit_rate:.2f}% | 고점: {bot_settings.highest_profit_rate:.2f}% | SL: {effective_sl:.2f}%")

                # ── 미보유 — 1차 매수 ────────────────────────────────
                elif coin_balance <= 0.0001:
                    # C. 일일 손실 한도 체크
                    if _check_daily_loss(db, bot_settings):
                        await asyncio.sleep(60)
                        continue
                    # C. 연속 손절 쿨다운 체크
                    if _check_consecutive_loss(db, bot_settings):
                        await asyncio.sleep(60)
                        continue

                    if current_rsi and current_rsi <= bot_settings.rsi_threshold:
                        # A. 볼린저밴드 필터
                        boll_ok = not bot_settings.use_bollinger or strategy.is_below_bollinger_lower(target_exchange)
                        # A. MACD 반전 필터
                        macd_ok = not bot_settings.use_macd or strategy.is_macd_reversing(target_exchange)
                        # A. 거래량 급증 필터
                        vol_ok = not bot_settings.use_volume_filter or strategy.is_volume_surging(
                            target_exchange, multiplier=bot_settings.volume_multiplier or 1.5
                        )

                        filters = {"볼린저": boll_ok, "MACD": macd_ok, "거래량": vol_ok}
                        failed = [k for k, v in filters.items() if not v]
                        if failed:
                            logger.info(f"[대기] RSI {current_rsi:.2f} 충족, 필터 미달: {', '.join(failed)}")
                        else:
                            krw_balance = current_client.get_krw_balance()
                            if krw_balance > 5000:
                                ratio = bot_settings.first_buy_ratio or 0.6
                                buy_amount = krw_balance * ratio * 0.995
                                res = current_client.buy_market_order(buy_amount)
                                if res:
                                    bot_settings.avg_buy_price = current_price
                                    bot_settings.highest_profit_rate = 0.0
                                    bot_settings.buy_count = 1
                                    bot_settings.position_opened_at = dt.datetime.utcnow()
                                    _record_buy(db, current_price, buy_amount)
                                    db.commit()
                                    logger.info(f"🛒 1차 매수: {current_price:,.0f} | RSI: {current_rsi:.2f} | 금액: {buy_amount:,.0f} KRW")
                                    filter_str = f"RSI {current_rsi:.2f}"
                                    if bot_settings.use_bollinger: filter_str += " | 볼린저✓"
                                    if bot_settings.use_macd: filter_str += " | MACD✓"
                                    if bot_settings.use_volume_filter: filter_str += " | 거래량✓"
                                    send_discord_message("🛒 1차 매수", f"{filter_str}\n체결가: {current_price:,.0f}\n매수금액: {buy_amount:,.0f} KRW", color=0x00ff00)
                                else:
                                    logger.error("❌ 1차 매수 실패")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"[Trading Loop Error] {e}")
            send_discord_message("⚠️ 봇 오류", str(e), color=0xffa500)

        await asyncio.sleep(60)

# --- Auth Dependency ---
def get_current_user(request: Request):
    """
    Checks for a valid session token in cookie.
    """
    session = request.cookies.get("session_auth")
    if session != SESSION_SECRET_KEY:
        return None
    return True

def verify_csrf(request: Request):
    """
    Verifies CSRF token for POST/PUT/DELETE requests.
    """
    if request.method in ["POST", "PUT", "DELETE"]:
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token or csrf_token != CSRF_SECRET:
            raise HTTPException(status_code=403, detail="CSRF Token Mismatch")

# --- Web Dashboard Routes ---
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": error}
    )

@app.post("/login")
async def login(request: Request, response: Response, password: str = Form(...)):
    client_ip = request.client.host
    now = time.time()
    
    # Check if IP is blocked
    attempt_info = LOGIN_ATTEMPTS.get(client_ip, {"count": 0, "blocked_until": 0})
    if now < attempt_info["blocked_until"]:
        wait_time = int(attempt_info["blocked_until"] - now)
        return templates.TemplateResponse(
            request=request, name="login.html", 
            context={"error": f"Too many attempts. Blocked for {wait_time}s."}
        )

    if password == DASHBOARD_PASSWORD:
        # Reset counter on success
        LOGIN_ATTEMPTS[client_ip] = {"count": 0, "blocked_until": 0}
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="session_auth", 
            value=SESSION_SECRET_KEY, 
            httponly=True, 
            max_age=86400,
            samesite="lax",
            secure=False # Set to True if using HTTPS
        )
        return response
    
    # Track failed attempts
    new_count = attempt_info["count"] + 1
    blocked_until = 0
    if new_count >= MAX_LOGIN_ATTEMPTS:
        blocked_until = now + LOCKOUT_DURATION
        logger.warning(f"🔒 Brute-force detected: IP {client_ip} blocked until {blocked_until}")
        error_msg = f"Access Denied. Too many failures. Blocked for {LOCKOUT_DURATION//60} mins."
    else:
        LOGIN_ATTEMPTS[client_ip] = {"count": new_count, "blocked_until": 0}
        error_msg = f"Invalid Passcode ({new_count}/{MAX_LOGIN_ATTEMPTS})."

    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": error_msg}
    )

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_auth")
    return response

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request, name="index.html", context={"csrf_token": CSRF_SECRET}
    )

@app.get("/api/status")
async def get_status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        
        bot_settings = db.query(BotSettings).first()
        target_exchange = bot_settings.exchange or "BITHUMB"
        current_client = get_client(target_exchange)
        authorized = is_client_authorized(target_exchange)
        
        krw_balance = current_client.get_krw_balance() or 0.0 if authorized else 0.0
        coin_balance = current_client.get_coin_balance(SYMBOL) or 0.0 if authorized else 0.0
        
        current_price = current_client.get_current_price(SYMBOL)
        if current_price is None:
            logger.warning(f"[Status] {target_exchange} 현재가 조회 실패, BITHUMB fallback 시도")
            current_price = bithumb_client.get_current_price(SYMBOL) if bithumb_client else None
        current_rsi = (strategy.get_rsi("BITHUMB") if strategy else None) or 0.0

        profit_rate = 0.0
        if bot_settings and bot_settings.avg_buy_price > 0 and current_price:
            profit_rate = ((current_price / bot_settings.avg_buy_price) - 1) * 100
        
        # Calculate Detailed Statistics
        all_trades = db.query(TradeHistory).filter(TradeHistory.side == "SELL").order_by(TradeHistory.timestamp.asc()).all()
        total_net_profit = sum([t.net_profit for t in all_trades if t.net_profit is not None])
        win_count = len([t for t in all_trades if t.net_profit is not None and t.net_profit > 0])
        loss_count = len([t for t in all_trades if t.net_profit is not None and t.net_profit < 0])
        win_rate = (win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0.0

        # 평균 매매 단가 (매도당 평균 순익)
        trade_count = win_count + loss_count
        avg_profit_per_trade = int(total_net_profit / trade_count) if trade_count > 0 else 0

        # 오늘 손익
        import datetime as dt
        today_start = dt.datetime.combine(dt.date.today(), dt.time.min)
        today_trades = [t for t in all_trades if t.timestamp >= today_start and t.net_profit is not None]
        today_net_profit = int(sum(t.net_profit for t in today_trades))

        # 마지막 매매 경과시간
        last_trade = db.query(TradeHistory).order_by(TradeHistory.timestamp.desc()).first()
        if last_trade:
            elapsed = dt.datetime.utcnow() - last_trade.timestamp
            elapsed_minutes = int(elapsed.total_seconds() / 60)
        else:
            elapsed_minutes = None
        
        # Prepare Chart Data (Cumulative Profit Over Time)
        cumulative_profits = []
        current_sum = 0
        for t in all_trades:
            if t.net_profit is not None:
                current_sum += t.net_profit
                cumulative_profits.append({
                    "x": t.timestamp.strftime("%m-%d %H:%M"),
                    "y": current_sum
                })

        # strategy가 초기화 실패한 경우 fallback 생성
        _strategy = strategy if strategy is not None else ScalperStrategy()

        # OHLCV 캔들 데이터 (15분봉 50개) — 봇 정지 상태에서도 항상 조회
        # BITHUMB public API 우선 사용 (인증 불필요, 안정적)
        candle_data = []
        try:
            ohlcv_df = _strategy.get_ohlcv("BITHUMB", interval="minute15", count=50)
            if ohlcv_df is None or ohlcv_df.empty:
                ohlcv_df = _strategy.get_ohlcv(target_exchange, interval="minute15", count=50)
            if ohlcv_df is not None and not ohlcv_df.empty:
                # 인덱스가 datetime이 아닐 수 있으므로 컬럼에서 시각 추출
                time_col = None
                for col in ("candle_date_time_kst", "candle_date_time_utc", "timestamp"):
                    if col in ohlcv_df.columns:
                        time_col = col
                        break
                for i, row in ohlcv_df.iterrows():
                    try:
                        if time_col:
                            import pandas as _pd
                            ts_str = str(row[time_col])[:16].replace("T", " ")
                        else:
                            # fallback: 인덱스가 datetime인 경우
                            ts_str = i.strftime("%m-%d %H:%M") if hasattr(i, "strftime") else str(i)[:16]
                        candle_data.append({
                            "x": ts_str,
                            "o": round(float(row["open"]), 0),
                            "h": round(float(row["high"]), 0),
                            "l": round(float(row["low"]), 0),
                            "c": round(float(row["close"]), 0),
                        })
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"[OHLCV] 캔들 데이터 조회 실패: {e}")

        # 지표 계산용 exchange: BITHUMB public API 우선 (인증 불필요)
        indicator_exchange = "BITHUMB"

        # Bollinger Band values
        boll_upper, boll_middle, boll_lower = _strategy.get_bollinger(indicator_exchange)
        boll_ok = bool(_strategy.is_below_bollinger_lower(indicator_exchange)) if boll_lower is not None else None

        # MACD values
        macd_val, macd_signal, macd_hist = _strategy.get_macd(indicator_exchange)
        macd_reversing = bool(_strategy.is_macd_reversing(indicator_exchange)) if macd_hist else None

        # Volume ratio
        vol_current, vol_avg, vol_ratio = _strategy.get_volume_ratio(indicator_exchange)
        vol_surging = bool(_strategy.is_volume_surging(
            indicator_exchange,
            multiplier=bot_settings.volume_multiplier if bot_settings else 1.5
        )) if vol_ratio is not None else None

        # Full trade history (all records, newest first)
        history = db.query(TradeHistory).order_by(TradeHistory.timestamp.desc()).all()

        return {
            "exchange": target_exchange,
            "authorized": authorized,
            "is_running": bot_settings.is_running if bot_settings else False,
            "target_coin": SYMBOL,
            "krw_balance": int(krw_balance),
            "coin_balance": coin_balance,
            "current_price": int(current_price) if current_price else 0,
            "current_rsi": current_rsi,
            "bollinger": {
                "upper": int(boll_upper) if boll_upper else None,
                "middle": int(boll_middle) if boll_middle else None,
                "lower": int(boll_lower) if boll_lower else None,
                "is_below": boll_ok,
            },
            "macd": {
                "histogram": round(macd_hist[-1], 2) if macd_hist else None,
                "histogram_prev": round(macd_hist[-2], 2) if macd_hist and len(macd_hist) >= 2 else None,
                "is_reversing": macd_reversing,
            },
            "volume": {
                "current": round(vol_current, 4) if vol_current else None,
                "avg": round(vol_avg, 4) if vol_avg else None,
                "ratio": round(vol_ratio, 2) if vol_ratio else None,
                "is_surging": vol_surging,
            },
            "avg_buy_price": int(bot_settings.avg_buy_price) if bot_settings else 0,
            "profit_rate": profit_rate,
            "total_net_profit": int(total_net_profit),
            "win_rate": win_rate,
            "win_count": win_count,
            "loss_count": loss_count,
            "avg_profit_per_trade": avg_profit_per_trade,
            "today_net_profit": today_net_profit,
            "last_trade_elapsed_minutes": elapsed_minutes,
            "chart_data": cumulative_profits,
            "candle_data": candle_data,
            "buy_count": bot_settings.buy_count if bot_settings else 0,
            "config": {
                "rsi_threshold": bot_settings.rsi_threshold if bot_settings else 35.0,
                "rsi_threshold_2": bot_settings.rsi_threshold_2 if bot_settings else 28.0,
                "target_profit_rate": bot_settings.target_profit_rate if bot_settings else 1.5,
                "stop_loss_rate": bot_settings.stop_loss_rate if bot_settings else -1.0,
                "trailing_offset": bot_settings.trailing_stop_offset if bot_settings else 0.3,
                "use_bollinger": bot_settings.use_bollinger if bot_settings else True,
                "first_buy_ratio": bot_settings.first_buy_ratio if bot_settings else 0.6,
                "use_macd": bot_settings.use_macd if bot_settings else True,
                "use_volume_filter": bot_settings.use_volume_filter if bot_settings else True,
                "volume_multiplier": bot_settings.volume_multiplier if bot_settings else 1.5,
                "atr_multiplier": bot_settings.atr_multiplier if bot_settings else 1.5,
                "daily_loss_limit": bot_settings.daily_loss_limit if bot_settings else -50000.0,
                "max_consecutive_loss": bot_settings.max_consecutive_loss if bot_settings else 3,
                "cooldown_minutes": bot_settings.cooldown_minutes if bot_settings else 60,
            },
            "history": [{
                "id": h.id, "side": h.side, "price": int(h.price), "volume": h.volume,
                "total_amount": int(h.total_amount), "net_profit": int(h.net_profit) if h.net_profit else 0,
                "fee": int(h.fee) if h.fee else 0,
                "timestamp": (h.timestamp + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
            } for h in history]
        }
    except Exception:
        traceback.print_exc()
        return {"status": "error", "message": "Check server terminal for traceback"}

@app.post("/api/settings")
async def update_settings(data: SettingsUpdate, db: Session = Depends(get_db), user=Depends(get_current_user), _=Depends(verify_csrf)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        bot_settings = db.query(BotSettings).first()
        if bot_settings:
            bot_settings.rsi_threshold = data.rsi_threshold
            bot_settings.rsi_threshold_2 = data.rsi_threshold_2
            bot_settings.target_profit_rate = data.target_profit_rate
            bot_settings.stop_loss_rate = data.stop_loss_rate
            bot_settings.trailing_stop_offset = data.trailing_offset
            bot_settings.exchange = data.exchange
            bot_settings.use_bollinger = data.use_bollinger
            bot_settings.first_buy_ratio = data.first_buy_ratio
            bot_settings.use_macd = data.use_macd
            bot_settings.use_volume_filter = data.use_volume_filter
            bot_settings.volume_multiplier = data.volume_multiplier
            bot_settings.atr_multiplier = data.atr_multiplier
            bot_settings.daily_loss_limit = data.daily_loss_limit
            bot_settings.max_consecutive_loss = data.max_consecutive_loss
            bot_settings.cooldown_minutes = data.cooldown_minutes
            db.commit()
            return {"status": "success"}
        return {"status": "error", "message": "Bot settings not found"}
    except Exception:
        traceback.print_exc()
        return {"status": "error", "message": "Internal server error. Check logs."}

@app.post("/api/sell_now")
async def sell_now(db: Session = Depends(get_db), user=Depends(get_current_user), _=Depends(verify_csrf)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    bot_settings = db.query(BotSettings).first()
    target_exchange = (bot_settings.exchange or "BITHUMB") if bot_settings else "BITHUMB"
    current_client = get_client(target_exchange)

    if not is_client_authorized(target_exchange):
        return {"status": "error", "message": "API not authorized"}

    coin_balance = current_client.get_coin_balance(SYMBOL)
    if not coin_balance or coin_balance <= 0.0001:
        return {"status": "error", "message": "No coin balance to sell"}

    current_price = current_client.get_current_price(SYMBOL)
    res = current_client.sell_market_order(coin_balance)
    if res:
        net_profit = _record_sell(db, current_price, coin_balance, bot_settings)
        logger.info(f"[즉시매도] SOLD {coin_balance} at {current_price} (P&L: {net_profit:,.0f} KRW)")
        send_discord_message("🔴 즉시매도 실행", f"{SYMBOL} {coin_balance} 전량 매도\n체결가: {current_price}\n손익: {net_profit:,.0f} KRW", color=0xe63946)
        return {"status": "success", "net_profit": int(net_profit)}

    return {"status": "error", "message": "Order failed"}

@app.post("/api/toggle")
async def toggle_bot(db: Session = Depends(get_db), user=Depends(get_current_user), _=Depends(verify_csrf)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    bot_settings = db.query(BotSettings).first()
    if not bot_settings:
        bot_settings = BotSettings(is_running=False)
        db.add(bot_settings)
    
    bot_settings.is_running = not bot_settings.is_running
    db.commit()
    
    msg = "Bot started!" if bot_settings.is_running else "Bot stopped."
    send_discord_message("🤖 Bot Status Changed", msg, color=0x3498db)
    return {"status": "success", "is_running": bot_settings.is_running}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
