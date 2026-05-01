import streamlit as st
import pandas as pd
import MetaTrader5 as mt5
import os
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION ---
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

def load_config():
    with open(ROOT / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

# --- MT5 CONNECTION ---
def init_mt5():
    if not mt5.initialize(
        path=os.getenv("MT5_PATH"),
        login=int(os.getenv("MT5_LOGIN")),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER")
    ):
        st.error(f"MT5 Initialization Failed: {mt5.last_error()}")
        return False
    return True

# --- STREMLIT UI ---
st.set_page_config(page_title="TITAN PORTFOLIO DASHBOARD", layout="wide")

st.title("🏆 TITAN PORTFOLIO MONITOR")
st.subheader("Mission to $100,000 - Real-time Performance Tracking")

if init_mt5():
    # 1. Account Summary
    acc = mt5.account_info()
    col1, col2, col3, col4 = st.columns(4)
    if acc:
        col1.metric("Balance", f"${acc.balance:,.2f}")
        col2.metric("Equity", f"${acc.equity:,.2f}")
        col3.metric("Margin Level", f"{acc.margin_level:.1f}%")
        profit_color = "normal" if acc.profit >= 0 else "inverse"
        col4.metric("Floating PNL", f"${acc.profit:,.2f}", delta_color=profit_color)

    # 2. Active Positions
    st.write("---")
    st.header("🎯 Active Positions")
    positions = mt5.positions_get()
    if positions:
        df_pos = pd.DataFrame([p._asdict() for p in positions])
        # Clean up columns for display
        df_display = df_pos[['symbol', 'type', 'volume', 'price_open', 'price_current', 'sl', 'tp', 'profit', 'comment']]
        df_display['type'] = df_display['type'].apply(lambda x: 'BUY' if x == 0 else 'SELL')
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("No active positions at the moment.")

    # 3. Market Watch
    st.write("---")
    st.header("🌍 Market Watch")
    symbols = list(config["symbols"].keys())
    mcol1, mcol2, mcol3 = st.columns(3)
    for i, sym in enumerate(symbols):
        tick = mt5.symbol_info_tick(sym)
        if tick:
            col = [mcol1, mcol2, mcol3][i % 3]
            col.write(f"**{sym}** | Bid: {tick.bid} | Ask: {tick.ask}")

    # 4. Bot Logs (Tail)
    st.write("---")
    st.header("📜 Live Bot Intelligence")
    log_path = ROOT / "logs" / "gold_trading_bot.log"
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            st.code("".join(lines[-15:]), language="text")
    
    # Auto Refresh
    time.sleep(5)
    st.rerun()

mt5.shutdown()
