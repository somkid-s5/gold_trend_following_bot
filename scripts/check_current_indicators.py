from __future__ import annotations
import os
from pathlib import Path
import MetaTrader5 as mt5
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import load_config, build_strategy, load_dotenv

def main():
    load_dotenv(ROOT / ".env")
    config = load_config(ROOT / "config" / "config.yaml")
    
    login = int(os.getenv("MT5_LOGIN"))
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    path = os.getenv("MT5_PATH")

    if not mt5.initialize(path=path, login=login, password=password, server=server):
        print(f"Failed to connect: {mt5.last_error()}")
        return

    symbol = "XAUUSDm"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 400)
    mt5.shutdown()

    if rates is None:
        print("Failed to fetch rates")
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Calculate Indicators
    ema_fast = df['close'].ewm(span=config['strategies']['trend_following']['fast_ema'], adjust=False).mean()
    ema_slow = df['close'].ewm(span=config['strategies']['trend_following']['slow_ema'], adjust=False).mean()
    
    # RSI calculation
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    last_close = df['close'].iloc[-1]
    last_fast = ema_fast.iloc[-1]
    last_slow = ema_slow.iloc[-1]
    last_rsi = rsi.iloc[-1]

    print(f"--- CURRENT MARKET STATUS ({symbol}) ---")
    print(f"Price: {last_close:.2f}")
    print(f"EMA 34 (Fast): {last_fast:.2f}")
    print(f"EMA 150 (Slow): {last_slow:.2f}")
    print(f"RSI (14): {last_rsi:.2f}")
    print(f"EMA Gap: {abs(last_fast - last_slow):.2f}")
    
    if last_fast > last_slow:
        print("Trend: BULLISH (EMA 34 > EMA 150)")
        print(f"Wait for RSI to cross ABOVE {config['strategies']['trend_following']['rsi_buy_level']} for BUY")
    else:
        print("Trend: BEARISH (EMA 34 < EMA 150)")
        print(f"Wait for RSI to cross BELOW {config['strategies']['trend_following']['rsi_sell_level']} for SELL")

if __name__ == "__main__":
    main()
