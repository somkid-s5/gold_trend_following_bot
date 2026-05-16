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

def fetch_data(symbol, timeframe_mt5, years=5):
    print(f"Fetching {years} years of data for {symbol}...")
    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=years * 365)
    
    rates = mt5.copy_rates_range(symbol, timeframe_mt5, utc_from, utc_to)
    if rates is None:
        print(f"Failed to fetch data: {mt5.last_error()}")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df

def run_compounding_simulation(start_bal=200.0, dep=200.0):
    load_dotenv()
    config = load_config()
    
    if not mt5.initialize(
        login=int(os.getenv("MT5_LOGIN")),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER")
    ):
        print("MT5 Init Failed")
        return

    symbol = config["trading"]["symbol"]
    tf_map = {"H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15}
    timeframe = tf_map.get(config["strategies"]["trend_following"]["timeframe"], mt5.TIMEFRAME_H1)
    
    data = fetch_data(symbol, timeframe, years=5)
    mt5.shutdown()
    
    if data is None or data.empty:
        return

    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = TrendFollowing(config["strategies"]["trend_following"])
    exit_manager = ExitManager()
    
    balance = start_bal
    monthly_deposit = dep
    
    trades = []
    yearly_stats = {}
    
    prepared_data = strategy.prepare_data(data)
    tick_size = config["symbols"][symbol]["point"]
    tick_value = config["symbols"][symbol]["contract_size"] * tick_size
    
    last_deposit_month = -1
    total_deposited = balance

    warmup = 1500
    
    print(f"Starting Simulation with Correct History Passing...")
    
    for i in range(warmup, len(prepared_data) - 1):
        current_row = prepared_data.iloc[i]
        next_row = prepared_data.iloc[i+1]
        curr_time = current_row['time']
        
        # Monthly Deposit
        if curr_time.month != last_deposit_month:
            if last_deposit_month != -1: 
                balance += monthly_deposit
                total_deposited += monthly_deposit
            last_deposit_month = curr_time.month
            risk_manager.update_equity_state(balance, balance)

        # Signal Generation - PASS HISTORY (approx 100 bars enough for daily range)
        history_window = prepared_data.iloc[i-100 : i+1]
        signals = strategy.generate_signals(history_window)
        
        if signals:
            signal = max(signals, key=lambda x: x.confidence)
            risk_dist = abs(signal.entry - signal.sl)
            
            lot = risk_manager.calculate_lot(
                symbol=symbol,
                equity=balance,
                risk_pct=config["risk"]["risk_per_trade_pct"],
                sl_distance_price=risk_dist,
                tick_size=tick_size,
                tick_value=tick_value
            )
            
            h, l, c = float(next_row['high']), float(next_row['low']), float(next_row['close'])
            sl_price = exit_manager.calculate_managed_sl(signal.action, signal.entry, signal.sl, h if signal.action == "BUY" else l, risk_dist, tick_size)
            
            exit_price = c
            if signal.action == "BUY":
                if l <= sl_price: exit_price = sl_price
                elif h >= signal.tp: exit_price = signal.tp
            else:
                if h >= sl_price: exit_price = sl_price
                elif l <= signal.tp: exit_price = signal.tp
                
            pnl = (exit_price - signal.entry) / tick_size * tick_value * lot if signal.action == "BUY" else (signal.entry - exit_price) / tick_size * tick_value * lot
            
            balance += pnl
            risk_manager.update_trade_outcome(pnl)
            risk_manager.update_equity_state(balance, balance)
            trades.append(pnl)

        year = curr_time.year
        if year not in yearly_stats:
            yearly_stats[year] = balance

    print(f"\nSimulation Results (Fixed):")
    for year, bal in yearly_stats.items():
        print(f"Year {year} End: ${bal:,.2f}")
    
    print("\n" + "="*40)
    print(f"Total Invested: ${total_deposited:,.2f}")
    print(f"Final Balance: ${balance:,.2f}")
    print(f"Total Trades: {len(trades)}")
    print("="*40)

if __name__ == "__main__":
    run_compounding_simulation(200.0, 200.0)
