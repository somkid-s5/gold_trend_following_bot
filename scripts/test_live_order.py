from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import load_dotenv, load_config, apply_env_overrides
from src.broker.mt5_connector import MT5Connector

def main():
    # โหลดการตั้งค่าและเชื่อมต่อ MT5
    load_dotenv(ROOT / ".env")
    config = apply_env_overrides(load_config(ROOT / "config" / "config.yaml"))
    
    print("🔄 Connecting to MT5...")
    connector = MT5Connector(config["mt5"])
    connector.connect_mt5()
    
    symbol = "XAUUSD"
    volume = float(config["symbols"][symbol]["min_lot"]) # เทสต์ด้วยหลอดเล็กสุด (0.01)
    
    try:
        print(f"📡 Fetching tick data for {symbol}...")
        tick = connector.get_symbol_tick(symbol)
        ask_price = tick.ask
        
        # ตั้ง SL/TP ขำๆ ป้องกันความเสี่ยง (ห่าง 2 ดอลลาร์)
        sl = ask_price - 2.0
        tp = ask_price + 2.0
        
        print(f"🚀 Sending BUY order: {volume} lot {symbol} at Market Price (~{ask_price})")
        print(f"🛡️ SL: {sl} | 🎯 TP: {tp}")
        
        # ส่งคำสั่งเปิดออเดอร์
        result = connector.send_order(
            symbol=symbol,
            action="BUY",
            volume=volume,
            sl=sl,
            tp=tp,
            comment="live_test_order"
        )
        print("✅ Order opened successfully!")
        
        ticket = result.get("order")
        
        if ticket:
            print(f"⏳ Waiting 5 seconds before closing ticket #{ticket}...")
            time.sleep(5)
            
            # ส่งคำสั่งปิดออเดอร์
            print("🛑 Closing position...")
            close_result = connector.close_position(ticket)
            print("✅ Position closed successfully!")
        else:
            print("⚠️ Could not find ticket ID to close it automatically. Please check your MT5 Terminal.")
            
    except Exception as e:
        print(f"❌ Failed to execute: {e}")
        
    finally:
        connector.disconnect()
        print("🔌 Disconnected from MT5.")

if __name__ == "__main__":
    main()
