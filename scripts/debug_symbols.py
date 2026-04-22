import MetaTrader5 as mt5
import os
from pathlib import Path

def main():
    path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
    if not mt5.initialize(path=path, login=433209659, password="#Somkid@exne55", server="Exness-MT5Trial7"):
        print(f"Failed to connect: {mt5.last_error()}")
        return

    symbols = mt5.symbols_get()
    print("--- SYMBOLS IN MARKET WATCH ---")
    visible_symbols = [s.name for s in symbols if s.visible]
    for name in visible_symbols:
        print(f"- {name}")
    
    if "XAUUSDm" in visible_symbols:
        print("\nSUCCESS: Found XAUUSDm (with small m)")
    elif "XAUUSDM" in visible_symbols:
        print("\nSUCCESS: Found XAUUSDM (with large M)")
    else:
        print("\nWARNING: Gold symbol not found in visible list. Try adding it to Market Watch.")

    mt5.shutdown()

if __name__ == "__main__":
    main()
