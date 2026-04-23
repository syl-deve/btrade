import requests
import datetime
from config import DISCORD_WEBHOOK_URL

def send_discord_message(title: str, description: str, color: int = 0x00ff00):
    """
    Sends an embed message to the configured Discord channel using a webhook.
    
    :param title: Title of the embed
    :param description: Description/Content of the alert
    :param color: Decimal color code (default is Green)
    """
    if not DISCORD_WEBHOOK_URL:
        print("[Notifier] Discord Webhook URL is not set. Skipping notification.")
        return
    
    timestamp = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "footer": {
                    "text": f"BITRADE Alert | {timestamp}"
                }
            }
        ]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"[Notifier] Error sending discord message: {e}")
