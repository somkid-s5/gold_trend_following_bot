import MetaTrader5 as mt5
import pandas as pd
import os
from dotenv import load_dotenv
from pathlib import Path

def sync_data():
    load_dotenv()
    if not mt5.initialize(
        path=os.getenv("MT5_PATH"),
        login=int(os.getenv("MT5_LOGIN", 0)),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER")
    ):
        print(f"Failed to initialize: {mt5.last_error()}")
        return

    symbols = ["EURUSDm", "GBPUSDm", "XAUUSDm", "BTCUSDm"]
    for sym in symbols:
        print(f"🔄 Syncing {sym}...")
        mt5.symbol_select(sym, True)
        # Force download 100,000 bars
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 100000)
        if rates is not None:
            print(f"✅ {sym}: {len(rates)} bars synced.")
        else:
            print(f"❌ {sym}: Sync failed.")

    mt5.shutdown()

if __name__ == "__main__":
    sync_data()
