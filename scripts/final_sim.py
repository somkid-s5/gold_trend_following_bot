import os
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
from dotenv import load_dotenv
from pathlib import Path
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.risk.risk_manager import RiskManager
from src.strategies.trend_following import TrendFollowing
from src.core.exit_logic import ExitManager

def load_config():
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_simulation():
    load_dotenv()
    config = load_config()
    
    if not mt5.initialize(login=int(os.getenv("MT5_LOGIN")), password=os.getenv("MT5_PASSWORD"), server=os.getenv("MT5_SERVER")):
        print("MT5 Init Failed")
        return

    symbol = config["trading"]["symbol"]
    # Get max available data for H1
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 20000)
    mt5.shutdown()
    
    if rates is None:
        print("Data fetch failed")
        return
        
    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
    
    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = TrendFollowing(config["strategies"]["trend_following"])
    exit_manager = ExitManager()
    
    balance = 200.0
    monthly_deposit = 200.0
    total_deposited = 200.0
    
    last_month = data['time'].iloc[0].month
    warmup = 1500
    
    results = []
    
    print(f"Simulation Range: {data['time'].min()} to {data['time'].max()}")

    for i in range(warmup, len(data) - 1):
        row = data.iloc[i]
        next_row = data.iloc[i+1]
        
        # Deposit on 1st of every month
        if row['time'].month != last_month:
            balance += monthly_deposit
            total_deposited += monthly_deposit
            last_month = row['time'].month
            
        # Signal (Pass history)
        history = data.iloc[i-500 : i+1]
        signals = strategy.generate_signals(history)
        
        if signals:
            sig = max(signals, key=lambda x: x.confidence)
            risk_dist = abs(sig.entry - sig.sl)
            
            lot = risk_manager.calculate_lot(symbol, balance, 2.0, risk_dist, 0.01, 1.0) # Simplified tick
            
            # Simulated Execution
            h, l = float(next_row['high']), float(next_row['low'])
            # Update SL to Break-Even if 1.5x Risk reached
            be_sl = exit_manager.calculate_managed_sl(sig.action, sig.entry, sig.sl, h if sig.action=="BUY" else l, risk_dist, 0.01)
            
            # Simple Outcome
            exit_price = next_row['close']
            if sig.action == "BUY":
                if l <= be_sl: exit_price = be_sl
                elif h >= sig.tp: exit_price = sig.tp
            else:
                if h >= be_sl: exit_price = be_sl
                elif l <= sig.tp: exit_price = sig.tp
            
            pnl = (exit_price - sig.entry) * 100 * lot if sig.action=="BUY" else (sig.entry - exit_price) * 100 * lot
            balance += pnl
            risk_manager.update_trade_outcome(pnl)
            results.append({"time": row['time'], "bal": balance})

    print(f"\nFINAL RESULTS:")
    print(f"Invested: ${total_deposited:,.2f}")
    print(f"Ending Balance: ${balance:,.2f}")
    print(f"Net Profit: ${balance - total_deposited:,.2f}")
    print(f"Total Trades: {len(results)}")

if __name__ == "__main__":
    run_simulation()
