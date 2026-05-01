import os
import sys
from pathlib import Path
import yaml
from datetime import datetime, timezone
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.telegram_notifier import TelegramNotifier
from src.utils.logger import setup_logger

def test_telegram():
    load_dotenv(ROOT / ".env")
    logger = setup_logger("telegram_test")
    
    with open(ROOT / "config" / "config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    notifier = TelegramNotifier(config.get("notifications", {}).get("telegram", {}), logger)
    
    if not notifier.is_enabled():
        print("❌ Telegram is NOT enabled or missing .env credentials!")
        print(f"BOT_TOKEN: {'FOUND' if os.getenv('TELEGRAM_BOT_TOKEN') else 'MISSING'}")
        print(f"CHAT_ID: {'FOUND' if os.getenv('TELEGRAM_CHAT_ID') else 'MISSING'}")
        return

    print("🚀 Sending test message to Telegram...")
    msg = notifier.build_event_message("Test", datetime.now(timezone.utc), "ระบบ TITAN $100k พร้อมรบแล้วครับลูกพี่! 💎🚀")
    
    try:
        success = notifier.send_message(msg)
        if success:
            print("✅ SUCCESS! Check your Telegram app.")
        else:
            print("⚠️ Failed to send message.")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    test_telegram()
