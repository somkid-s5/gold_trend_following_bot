import argparse
import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
import MetaTrader5 as mt5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import load_config
from src.strategies.trend_following import TrendFollowing
from src.risk.risk_manager import RiskManager

def fetch_history(symbol, days):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df

def run_multi_symbol_backtest():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    config = load_dotenv_vars(load_config(ROOT / "config" / "config.yaml"))
    symbols = ["XAUUSDm", "GBPUSDm", "EURUSDm"]
    
    if not mt5.initialize(
        path=config["mt5"]["path"],
        login=config["mt5"]["login"],
        password=os.getenv("MT5_PASSWORD"),
        server=config["mt5"]["server"]
    ):
        print(f"MT5 Init Failed")
        return

    print(f"🛡️ STARTING SECURE PORTFOLIO BACKTEST: {args.days} DAYS")
    
    data_map = {}
    for sym in symbols:
        df = fetch_history(sym, args.days)
        if not df.empty:
            data_map[sym] = df
            print(f"✅ {sym} loaded.")

    if not data_map: return

    balance = 10000.0
    initial_balance = balance
    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = TrendFollowing(config["strategies"]["trend_following"])
    all_times = sorted(list(set(pd.concat([df["time"] for df in data_map.values()]))))
    
    open_positions = [] # Track simulated open positions
    trades_count = 0
    max_equity = balance
    max_dd = 0
    
    print(f"🏃 Testing {len(all_times)} steps with Correlation Guard...")
    
    for i in range(100, len(all_times) - 1):
        t = all_times[i]
        risk_manager.update_equity_state(balance, balance)
        
        # 1. Close matured trades (simple simulation)
        # In a real backtest, we would track each bar. 
        # Here we just check for entries and use the next bar for outcome.
        
        for sym in symbols:
            if sym not in data_map: continue
            df = data_map[sym]
            match = df[df["time"] == t]
            if match.empty: continue
            
            idx = match.index[0]
            if idx < 100: continue
            
            # --- CORRELATION GUARD CHECK ---
            # Simulate open positions list for the manager
            sim_open = [{"symbol": trade["sym"]} for trade in open_positions]
            corr_decision = risk_manager.check_correlation(sym, sim_open)
            
            if not corr_decision.allowed:
                continue # Skip this symbol if too many USD pairs are open

            signals = strategy.generate_signals(df.iloc[idx-100:idx+1], {"symbol": sym})
            if signals:
                sig = max(signals, key=lambda x: x.confidence)
                s_cfg = config["symbols"][sym]
                ts, tv = float(s_cfg["point"]), float(s_cfg["contract_size"]) * float(s_cfg["point"])
                
                lot = risk_manager.calculate_lot(sym, balance, 0, 0, ts, tv)
                
                next_bar = df.iloc[idx+1]
                if sig.action == "BUY":
                    exit_p = sig.tp if next_bar["high"] >= sig.tp else (sig.sl if next_bar["low"] <= sig.sl else next_bar["close"])
                    pnl = (exit_p - sig.entry) / ts * tv * lot
                else:
                    exit_p = sig.tp if next_bar["low"] <= sig.tp else (sig.sl if next_bar["high"] >= sig.sl else next_bar["close"])
                    pnl = (sig.entry - exit_p) / ts * tv * lot
                
                balance += pnl
                risk_manager.update_trade_outcome(pnl)
                trades_count += 1
                
                # Metrics
                max_equity = max(max_equity, balance)
                dd = (max_equity - balance) / max_equity * 100
                max_dd = max(max_dd, dd)

        if i % 1000 == 0:
            print(f"📅 {t.strftime('%Y-%m')} | Equity: ${balance:,.2f} | MaxDD: {max_dd:.1f}%")

    print(f"\n🏁 FINAL SECURE RESULTS")
    print(f"💰 Net Profit: ${balance - initial_balance:,.2f}")
    print(f"📉 Max Drawdown: {max_dd:.2f}%")
    print(f"📈 Total ROI: {((balance - initial_balance)/initial_balance)*100:.2f}%")
    print(f"📊 Total Trades: {trades_count}")
    mt5.shutdown()

def load_dotenv_vars(config):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    config["mt5"]["login"] = int(os.getenv("MT5_LOGIN", config["mt5"]["login"]))
    config["mt5"]["password"] = os.getenv("MT5_PASSWORD")
    config["mt5"]["server"] = os.getenv("MT5_SERVER", config["mt5"]["server"])
    return config

if __name__ == "__main__":
    run_multi_symbol_backtest()
