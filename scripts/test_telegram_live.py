from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Add root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.telegram_notifier import TelegramNotifier
from src.utils.logger import setup_logger

def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists(): return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line: continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("#"): continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value

def run_live_telegram_test():
    load_dotenv(ROOT / ".env")
    logger = setup_logger("telegram_live_test")
    
    config = {
        "enabled": True,
        "summary_time_utc": "21:00",
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_CHAT_ID",
    }
    
    notifier = TelegramNotifier(config, logger)
    
    if not notifier.is_enabled():
        print("❌ ERROR: Telegram is not enabled. Please check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file.")
        return

    print("🚀 Starting Live Telegram Case Tests...")
    now = datetime.now(timezone.utc)

    # CASE 1: Basic Event (Startup)
    print("--- Sending Case 1: Startup Event ---")
    msg1 = notifier.build_event_message("Startup", now, "ระบบ TITAN Berserker เริ่มเดินเครื่องทดสอบแล้ว")
    success1 = notifier.send_message(msg1)
    print(f"Result: {'✅ Success' if success1 else '❌ Failed'}")

    # CASE 2: Guard Alert
    print("\n--- Sending Case 2: Guard Alert ---")
    msg2 = notifier.build_event_message("Guard Alert", now, "⚠️ ตรวจพบ Drawdown เกิน 5% ระบบหยุดเทรดชั่วคราวเพื่อความปลอดภัย")
    success2 = notifier.send_message(msg2)
    print(f"Result: {'✅ Success' if success2 else '❌ Failed'}")

    # CASE 3: Daily Summary (Financial Report)
    print("\n--- Sending Case 3: Daily Summary ---")
    mock_account = {"equity": 12500.50}
    mock_guard = {"status": "OK"}
    mock_trades = pd.DataFrame({"pnl": [150.20, -50.10, 300.45, 120.00]})
    
    # Mock connector object for capital detection
    class MockConnector:
        def get_total_invested_capital(self): return 10000.0
        
    msg3 = notifier.build_daily_summary(
        strategy_name="Titan_v18_Institutional",
        now_utc=now,
        account=mock_account,
        guard_payload=mock_guard,
        trades_frame=mock_trades,
        connector=MockConnector()
    )
    success3 = notifier.send_message(msg3)
    print(f"Result: {'✅ Success' if success3 else '❌ Failed'}")

    print("\n🏁 All test cases sent. Please check your Telegram app!")

if __name__ == "__main__":
    run_live_telegram_test()
