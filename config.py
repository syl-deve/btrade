import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BITHUMB_ACCESS_KEY = str(os.getenv("BITHUMB_ACCESS_KEY") or "").strip("'\" ")
BITHUMB_SECRET_KEY = str(os.getenv("BITHUMB_SECRET_KEY") or "").strip("'\" ")
DISCORD_WEBHOOK_URL = str(os.getenv("DISCORD_WEBHOOK_URL") or "").strip("'\" ")
ADMIN_USERNAME = str(os.getenv("ADMIN_USERNAME", "admin")).strip("'\" ")
ADMIN_PASSWORD_HASH = str(os.getenv("ADMIN_PASSWORD_HASH") or "").strip("'\" ")
DASHBOARD_PASSWORD = str(os.getenv("DASHBOARD_PASSWORD") or "").strip("'\" ")

# Security Check
if not ADMIN_PASSWORD_HASH:
    print("\n" + "!" * 50)
    print("WARNING: ADMIN_PASSWORD_HASH is not configured.")
    print("Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH in your .env file.")
    if DASHBOARD_PASSWORD:
        print("Legacy DASHBOARD_PASSWORD fallback is enabled temporarily.")
    print("!" * 50 + "\n")

# Core Settings
EXCHANGE = "BITHUMB"
SYMBOL = str(os.getenv("SYMBOL", "KRW-BTC")).strip("'\" ")
TRADING_INTERVAL_MINUTES = int(str(os.getenv("TRADING_INTERVAL_MINUTES", "1")).strip("'\" "))

# Database Configuration
DATABASE_URL = "sqlite:///./trading_bot.db"
