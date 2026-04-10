import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

UPBIT_ACCESS_KEY = str(os.getenv("UPBIT_ACCESS_KEY") or "").strip("'\" ")
UPBIT_SECRET_KEY = str(os.getenv("UPBIT_SECRET_KEY") or "").strip("'\" ")
BITHUMB_ACCESS_KEY = str(os.getenv("BITHUMB_ACCESS_KEY") or "").strip("'\" ")
BITHUMB_SECRET_KEY = str(os.getenv("BITHUMB_SECRET_KEY") or "").strip("'\" ")
DISCORD_WEBHOOK_URL = str(os.getenv("DISCORD_WEBHOOK_URL") or "").strip("'\" ")
DASHBOARD_PASSWORD = str(os.getenv("DASHBOARD_PASSWORD", "admin1234")).strip("'\" ")

# Security Check
if DASHBOARD_PASSWORD == "admin1234":
    print("\n" + "!" * 50)
    print("⚠️  WARNING: DEFAULT DASHBOARD PASSWORD IN USE!")
    print("Please change 'DASHBOARD_PASSWORD' in your .env file immediately.")
    print("!" * 50 + "\n")

# Core Settings
EXCHANGE = str(os.getenv("EXCHANGE", "UPBIT")).upper().strip("'\" ")
SYMBOL = str(os.getenv("SYMBOL", "KRW-BTC")).strip("'\" ")
TRADING_INTERVAL_MINUTES = int(str(os.getenv("TRADING_INTERVAL_MINUTES", "1")).strip("'\" "))

# Database Configuration
DATABASE_URL = "sqlite:///./trading_bot.db"
