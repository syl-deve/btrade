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
from core.upbit_client import UpbitClient
from core.bithumb_client import BithumbClient
from core.strategy import ScalperStrategy
from core.discord_notifier import send_discord_message
from contextlib import asynccontextmanager
import logging
import sys

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB (will create columns in fresh DB)
    init_db()
    
    # Ensure BotSettings exist
    db = SessionLocal()
    if not db.query(BotSettings).first():
        db.add(BotSettings(
            is_running=False, 
            avg_buy_price=0.0, 
            rsi_threshold=30.0,
            target_profit_rate=1.0, 
            stop_loss_rate=-2.0,
            highest_profit_rate=0.0,
            trailing_stop_offset=0.2
        ))
        db.commit()
    db.close()
    
    # Start the trading loop in the background
    task = asyncio.create_task(trading_loop())
    yield
    # Clean up (optional)
    task.cancel()

# FastAPI Setup
app = FastAPI(title="Upbit Auto-Trader Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global Client and Strategy Instances
upbit_client = None
bithumb_client = None
strategy = None

def init_clients():
    global upbit_client, bithumb_client, strategy
    try:
        upbit_client = UpbitClient()
        bithumb_client = BithumbClient()
        strategy = ScalperStrategy()
    except Exception:
        import traceback
        print("--- ERROR DURING CLIENT INITIALIZATION ---")
        traceback.print_exc()

init_clients()

def get_client(exchange="UPBIT"):
    if exchange == "BITHUMB":
        return bithumb_client
    return upbit_client

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Background Trading Task ---
async def trading_loop():
    """
    Main loop that periodically checks the market and executes trades.
    """
    logger.info("[Trading] Starting background loop...")
    while True:
        try:
            db = SessionLocal()
            bot_settings = db.query(BotSettings).first()
            if not bot_settings:
                # Initialize default settings if not exists
                bot_settings = BotSettings(is_running=False)
                db.add(bot_settings)
                db.commit()
                db.refresh(bot_settings)

            if bot_settings.is_running:
                # 0. Select Client based on DB
                target_exchange = bot_settings.exchange or "UPBIT"
                current_client = get_client(target_exchange)
                
                # 1. Fetch current data
                try:
                    logger.debug(f"DEBUG: Current price for {SYMBOL} ({target_exchange})...")
                    current_price = current_client.get_current_price(SYMBOL)
                    logger.debug(f"DEBUG: Current RSI...")
                    current_rsi = strategy.get_rsi()
                    logger.debug(f"DEBUG: Coin balance for {SYMBOL}...")
                    coin_balance = current_client.get_coin_balance(SYMBOL)
                    logger.debug(f"DEBUG: Data fetch complete. Price: {current_price}, RSI: {current_rsi}, Balance: {coin_balance}")
                except Exception:
                    print("--- ERROR IN TRADING LOOP DATA FETCH ---")
                    traceback.print_exc()
                    await asyncio.sleep(10)
                    continue
                
                # Safety Check: Skip if data is missing
                if current_price is None or coin_balance is None:
                    logger.warning(f"⚠️ Data missing from Exchange. Retrying in next loop...")
                    db.close()
                    await asyncio.sleep(10) # Quick retry
                    continue

                rsi_display = f"{current_rsi:.2f}" if current_rsi else "0.00"
                logger.info(f"[Checking] {SYMBOL} @ {current_price:,.0f} | RSI: {rsi_display} | Balance: {coin_balance:.6f}")

                # Check if we currently hold coins
                if coin_balance > 0.0001: 
                    if bot_settings.avg_buy_price > 0:
                        profit_rate = ((current_price / bot_settings.avg_buy_price) - 1) * 100
                        
                        # 1. Stop Loss (Emergency - Highest Priority)
                        if profit_rate <= bot_settings.stop_loss_rate:
                            res = current_client.sell_market_order(coin_balance)
                            if res:
                                buy_principle = bot_settings.avg_buy_price * coin_balance
                                sell_total = current_price * coin_balance
                                net_profit = sell_total - buy_principle
                                
                                new_trade = TradeHistory(
                                    symbol=SYMBOL, side="SELL", price=current_price, 
                                    volume=coin_balance, total_amount=sell_total,
                                    net_profit=net_profit
                                )
                                db.add(new_trade)
                                bot_settings.avg_buy_price = 0.0
                                bot_settings.highest_profit_rate = 0.0
                                db.commit()
                                logger.warning(f"🚨 Stop-Loss Triggered: SOLD at {current_price} (Loss: {profit_rate:.2f}%)")
                                send_discord_message(f"🚨 Emergency Stop-Loss: SELL", 
                                                    f"Panic sold at {current_price} due to {profit_rate:.2f}% loss. (Loss: {net_profit:,.0f} KRW)", 
                                                    color=0x0000ff)
                        
                        else:
                            # 2. Trailing Stop Logic (If not in Stop-Loss)
                            if profit_rate > bot_settings.highest_profit_rate:
                                bot_settings.highest_profit_rate = profit_rate
                                db.commit()

                            # Take Profit (Trailing Mode)
                            if bot_settings.highest_profit_rate >= bot_settings.target_profit_rate:
                                if profit_rate <= (bot_settings.highest_profit_rate - bot_settings.trailing_stop_offset):
                                    res = current_client.sell_market_order(coin_balance)
                                    if res:
                                        buy_principle = bot_settings.avg_buy_price * coin_balance
                                        sell_total = current_price * coin_balance
                                        net_profit = sell_total - buy_principle
                                        
                                        new_trade = TradeHistory(
                                            symbol=SYMBOL, side="SELL", price=current_price, 
                                            volume=coin_balance, total_amount=sell_total,
                                            net_profit=net_profit
                                        )
                                        db.add(new_trade)
                                        bot_settings.avg_buy_price = 0.0
                                        bot_settings.highest_profit_rate = 0.0
                                        db.commit()
                                        logger.info(f"🎣 Trailing Take-Profit: SOLD at {current_price} (Profit: {profit_rate:.2f}%)")
                                        send_discord_message(f"🎣 Trailing Take-Profit: SELL", 
                                                            f"Peak: {bot_settings.highest_profit_rate:.2f}%. Sold at {current_price} with {profit_rate:.2f}% profit. (Profit: +{net_profit:,.0f} KRW)", 
                                                            color=0xff0000)
                            else:
                                logger.info(f"[Holding] Current Profit: {profit_rate:.2f}% | Peak: {bot_settings.highest_profit_rate:.2f}% | Target: {bot_settings.target_profit_rate}%")
                else:
                    # 🛒 BUY Condition: RSI is low (Dynamic)
                    if current_rsi and current_rsi <= bot_settings.rsi_threshold:
                        logger.info(f"💎 BUY Signal Detected: RSI {current_rsi:.2f} <= {bot_settings.rsi_threshold}")
                        krw_balance = current_client.get_krw_balance()
                        if krw_balance > 5000:
                            buy_amount = krw_balance * 0.9995
                            res = current_client.buy_market_order(buy_amount)
                            if res:
                                bot_settings.avg_buy_price = current_price
                                bot_settings.highest_profit_rate = 0.0 # Reset peak on BUY
                                db.commit()
                                new_trade = TradeHistory(
                                    symbol=SYMBOL, side="BUY", price=current_price, 
                                    volume=buy_amount/current_price, total_amount=buy_amount
                                )
                                db.add(new_trade)
                                db.commit()
                                logger.info(f"🛒 BUY Entry Success: {SYMBOL} at {current_price} (Amount: {buy_amount:,.0f} KRW)")
                                send_discord_message(f"🛒 BUY Entry: {SYMBOL}", 
                                                    f"Bought at {current_price} due to RSI {current_rsi:.2f}", 
                                                    color=0x00ff00)
            db.close()
        except Exception as e:
            logger.error(f"[Trading Loop Error] {e}")
            send_discord_message("⚠️ Bot Error", f"An error occurred in the trading loop: {e}", color=0xffa500)
        
        await asyncio.sleep(60) # 1-minute interval for responsiveness

# --- Auth Dependency ---
def get_current_user(request: Request):
    """
    Checks for a valid session cookie. 
    Redirects to login if unauthorized.
    """
    session = request.cookies.get("session_auth")
    if session != DASHBOARD_PASSWORD:
        return None
    return True

# --- Web Dashboard Routes ---
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": error}
    )

@app.post("/login")
async def login(request: Request, response: Response, password: str = Form(...)):
    if password == DASHBOARD_PASSWORD:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="session_auth", value=DASHBOARD_PASSWORD, httponly=True, max_age=86400) # Valid for 1 day
        return response
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": "Invalid Passcode Access Denied."}
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
        request=request, name="index.html", context={}
    )

@app.get("/api/status")
async def get_status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        bot_settings = db.query(BotSettings).first()
        target_exchange = bot_settings.exchange or "UPBIT"
        current_client = get_client(target_exchange)
        
        krw_balance = current_client.get_krw_balance() or 0.0
        coin_balance = current_client.get_coin_balance(SYMBOL) or 0.0
        current_price = current_client.get_current_price(SYMBOL)
        current_rsi = strategy.get_rsi() or 0.0
        
        profit_rate = 0.0
        if bot_settings and bot_settings.avg_buy_price > 0 and current_price:
            profit_rate = ((current_price / bot_settings.avg_buy_price) - 1) * 100
        elif current_price is None:
            current_price = 0.0 # Safety default
        
        # Calculate Detailed Statistics
        all_trades = db.query(TradeHistory).filter(TradeHistory.side == "SELL").order_by(TradeHistory.timestamp.asc()).all()
        total_net_profit = sum([t.net_profit for t in all_trades if t.net_profit is not None])
        win_count = len([t for t in all_trades if t.net_profit is not None and t.net_profit > 0])
        loss_count = len([t for t in all_trades if t.net_profit is not None and t.net_profit < 0])
        win_rate = (win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0.0
        
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

        # Recent trade history
        history = db.query(TradeHistory).order_by(TradeHistory.timestamp.desc()).limit(10).all()
        
        return {
            "exchange": EXCHANGE,
            "is_running": bot_settings.is_running if bot_settings else False,
            "krw_balance": int(krw_balance),
            "coin_balance": coin_balance,
            "current_price": int(current_price),
            "current_rsi": current_rsi,
            "avg_buy_price": int(bot_settings.avg_buy_price) if bot_settings else 0,
            "profit_rate": profit_rate,
            "total_net_profit": int(total_net_profit),
            "win_rate": win_rate,
            "win_count": win_count,
            "loss_count": loss_count,
            "chart_data": cumulative_profits,
            "config": {
                "rsi_threshold": bot_settings.rsi_threshold if bot_settings else 30.0,
                "target_profit_rate": bot_settings.target_profit_rate if bot_settings else 1.0,
                "stop_loss_rate": bot_settings.stop_loss_rate if bot_settings else -2.0,
                "trailing_offset": bot_settings.trailing_stop_offset if bot_settings else 0.2
            },
            "history": [{
                "id": h.id, "side": h.side, "price": int(h.price), "volume": h.volume,
                "total_amount": int(h.total_amount), "net_profit": int(h.net_profit) if h.net_profit else 0,
                "timestamp": h.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            } for h in history]
        }
    except Exception:
        traceback.print_exc()
        return {"status": "error", "message": "Check server terminal for traceback"}

@app.post("/api/settings")
async def update_settings(data: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    bot_settings = db.query(BotSettings).first()
    if bot_settings:
        bot_settings.rsi_threshold = data.get("rsi_threshold", 30.0)
        bot_settings.target_profit_rate = data.get("target_profit_rate", 1.0)
        bot_settings.stop_loss_rate = data.get("stop_loss_rate", -2.0)
        bot_settings.trailing_stop_offset = data.get("trailing_offset", 0.2)
        bot_settings.exchange = data.get("exchange", "UPBIT")
        db.commit()
        return {"status": "success"}
    return {"status": "error"}

@app.post("/api/toggle")
async def toggle_bot(db: Session = Depends(get_db), user=Depends(get_current_user)):
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
