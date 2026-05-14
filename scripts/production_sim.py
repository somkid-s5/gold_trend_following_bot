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

def run_production_simulation():
    load_dotenv()
    config = load_config()
    
    if not mt5.initialize(login=int(os.getenv("MT5_LOGIN")), password=os.getenv("MT5_PASSWORD"), server=os.getenv("MT5_SERVER")):
        print("MT5 Init Failed")
        return

    symbol = config["trading"]["symbol"]
    # Get high quality H1 data (approx 5 years = 30000 bars)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 30000)
    mt5.shutdown()
    
    if rates is None:
        print("Data fetch failed")
        return
        
    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
    
    # Initialize using REAL production config
    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = TrendFollowing(config["strategies"]["trend_following"])
    exit_manager = ExitManager()
    
    # User Scenario
    balance = 200.0
    monthly_deposit = 200.0
    total_deposited = 200.0
    
    # Extract triggers from config
    be_trigger_rr = float(config["risk"].get("breakeven_rr_trigger", 1.0))
    
    last_month = data['time'].iloc[0].month
    warmup = 2000 # More warmup for EMA 200
    
    results = []
    equity_curve = []
    
    print(f"--- PRODUCTION SIMULATION START ---")
    print(f"Logic: Logic Parity v3 | Scaling: Titan v19 | RR: {config['strategies']['trend_following']['take_profit_rr']}")
    print(f"Range: {data['time'].min().date()} to {data['time'].max().date()}")

    for i in range(warmup, len(data) - 1):
        row = data.iloc[i]
        next_row = data.iloc[i+1]
        
        # Monthly Deposit Logic
        if row['time'].month != last_month:
            balance += monthly_deposit
            total_deposited += monthly_deposit
            last_month = row['time'].month
            risk_manager.update_equity_state(balance, balance)
            
        # Signal Generation (Pass enough history for indicators)
        history = data.iloc[i-500 : i+1]
        signals = strategy.generate_signals(history)
        
        if signals:
            sig = max(signals, key=lambda x: x.confidence)
            risk_dist = abs(sig.entry - sig.sl)
            
            # Use Production Lot Calculation
            lot = risk_manager.calculate_lot(
                symbol=symbol,
                equity=balance,
                sl_distance_price=risk_dist,
                tick_size=config["symbols"][symbol]["point"],
                tick_value=config["symbols"][symbol]["contract_size"] * config["symbols"][symbol]["point"]
            )
            
            # Simulated Execution
            h, l = float(next_row['high']), float(next_row['low'])
            
            # PRODUCTION v20 Logic
            instruction = exit_manager.calculate_v20_managed_exit(
                action=sig.action, 
                entry=sig.entry, 
                current_sl=sig.sl, 
                current_price=h if sig.action=="BUY" else l, 
                risk_dist=risk_dist, 
                point=config["symbols"][symbol]["point"],
                config=config["risk"]
            )
            
            current_lot = lot
            pnl_accum = 0.0
            res_str = "SL"
            
            # Simulate Partial TP
            if instruction.partial_close_pct > 0:
                partial_vol = round(current_lot * instruction.partial_close_pct, 2)
                if partial_vol >= 0.01:
                    # Profit from partial close (assumed at trigger price for simplicity)
                    partial_pnl = (risk_dist * 3.0) / config["symbols"][symbol]["point"] * (config["symbols"][symbol]["contract_size"] * config["symbols"][symbol]["point"]) * partial_vol
                    pnl_accum += partial_pnl
                    current_lot -= partial_vol
                    res_str = "PARTIAL_TP"

            # Outcome for remaining lot
            exit_price = next_row['close']
            hit_tp = False
            
            if sig.action == "BUY":
                if l <= instruction.new_sl: 
                    exit_price = instruction.new_sl
                elif h >= sig.tp: 
                    exit_price = sig.tp
                    hit_tp = True
            else:
                if h >= instruction.new_sl: 
                    exit_price = instruction.new_sl
                elif l <= sig.tp: 
                    exit_price = sig.tp
                    hit_tp = True
            
            rem_pnl = (exit_price - sig.entry) / config["symbols"][symbol]["point"] * (config["symbols"][symbol]["contract_size"] * config["symbols"][symbol]["point"]) * current_lot if sig.action=="BUY" else (sig.entry - exit_price) / config["symbols"][symbol]["point"] * (config["symbols"][symbol]["contract_size"] * config["symbols"][symbol]["point"]) * current_lot
            
            total_pnl = pnl_accum + rem_pnl
            balance += total_pnl
            risk_manager.update_trade_outcome(total_pnl)
            risk_manager.update_equity_state(balance, balance)
            
            if hit_tp: res_str = "TP"
            elif total_pnl >= 0 and res_str != "PARTIAL_TP": res_str = "BE"

            results.append({
                "time": row['time'], 
                "pnl": total_pnl, 
                "bal": balance, 
                "lot": lot, 
                "res": res_str
            })

    # Stats Calculation
    df_res = pd.DataFrame(results)
    win_rate = (df_res['pnl'] > 0).mean() * 100
    tp_count = (df_res['res'] == "TP").sum()
    be_count = (df_res['res'] == "BE").sum()
    sl_count = (df_res['res'] == "SL").sum()
    ptp_count = (df_res['res'] == "PARTIAL_TP").sum()

    print(f"\n--- FINAL PRODUCTION RESULTS (v20) ---")
    print(f"Total Invested: ${total_deposited:,.2f}")
    print(f"Final Balance: ${balance:,.2f}")
    print(f"Net Profit: ${balance - total_deposited:,.2f}")
    print(f"Growth: {((balance/total_deposited)-1)*100:.2f}%")
    print("-" * 30)
    print(f"Total Trades: {len(results)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Outcomes: TP: {tp_count} | Partial TP: {ptp_count} | BE/Lock: {be_count} | SL: {sl_count}")
    print(f"Max Lot Reached: {df_res['lot'].max()}")
    print("=" * 40)

if __name__ == "__main__":
    run_production_simulation()
