import os
from dotenv import load_dotenv
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

load_dotenv()

login = os.getenv("MT5_LOGIN")
password = os.getenv("MT5_PASSWORD")
server = os.getenv("MT5_SERVER")

print(f"Attempting to connect to {server} with login {login}...")

if not mt5.initialize(login=int(login), password=password, server=server):
    print(f"initialize() failed, error code = {mt5.last_error()}")
    quit()

print("Connection established!")

# Test fetching some history
symbol = "XAUUSD" # Try standard symbol
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
if rates is None:
    print(f"Failed to fetch XAUUSD, trying XAUUSDm...")
    symbol = "XAUUSDm"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)

if rates is not None:
    print(f"Successfully fetched {len(rates)} bars for {symbol}")
else:
    print("Failed to fetch data for both XAUUSD and XAUUSDm")

mt5.shutdown()
