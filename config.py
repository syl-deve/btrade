import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin1234")

# Core Settings
SYMBOL = os.getenv("SYMBOL", "KRW-BTC")
TRADING_INTERVAL_MINUTES = int(os.getenv("TRADING_INTERVAL_MINUTES", "15"))

# Database Configuration
DATABASE_URL = "sqlite:///./trading_bot.db"
