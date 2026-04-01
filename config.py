import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

UPBIT_ACCESS_KEY = str(os.getenv("UPBIT_ACCESS_KEY") or "").strip("'\" ")
UPBIT_SECRET_KEY = str(os.getenv("UPBIT_SECRET_KEY") or "").strip("'\" ")
DISCORD_WEBHOOK_URL = str(os.getenv("DISCORD_WEBHOOK_URL") or "").strip("'\" ")
DASHBOARD_PASSWORD = str(os.getenv("DASHBOARD_PASSWORD", "admin1234")).strip("'\" ")

# Core Settings
SYMBOL = str(os.getenv("SYMBOL", "KRW-BTC")).strip("'\" ")
TRADING_INTERVAL_MINUTES = int(str(os.getenv("TRADING_INTERVAL_MINUTES", "1")).strip("'\" "))

# Database Configuration
DATABASE_URL = "sqlite:///./trading_bot.db"
