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

from main import load_config, build_strategy
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

def run_dca_portfolio_backtest():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--balance", type=float, default=10000.0)
    parser.add_argument("--dca", type=float, default=150.0)
    args = parser.parse_args()

    # Load Env
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    config = load_config(ROOT / "config" / "config.yaml")
    symbols = list(config["symbols"].keys())
    
    if not mt5.initialize(
        path=os.getenv("MT5_PATH"),
        login=int(os.getenv("MT5_LOGIN", 0)),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER")
    ):
        print(f"MT5 Init Failed")
        return

    print(f"💰 UNIFIED DCA BACKTEST STARTING: ${args.balance}")
    
    data_map = {}
    for sym in symbols:
        print(f"📦 Fetching {sym}...")
        df = fetch_history(sym, args.days)
        if not df.empty:
            data_map[sym] = df

    balance = args.balance
    initial_balance = balance
    total_dca = 0.0
    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = build_strategy(config)
    all_times = sorted(list(set(pd.concat([df["time"] for df in data_map.values()]))))
    
    last_month = -1
    trades_count = 0
    max_equity = balance
    max_dd = 0

    for i in range(1200, len(all_times) - 1):
        t = all_times[i]
        if t.month != last_month:
            balance += args.dca
            total_dca += args.dca
            last_month = t.month

        risk_manager.update_equity_state(balance, balance)
        
        for sym in symbols:
            if sym not in data_map: continue
            df = data_map[sym]
            match = df[df["time"] == t]
            if match.empty: continue
            idx = match.index[0]
            if idx < 100: continue
            
            signals = strategy.generate_signals(df.iloc[idx-100:idx+1], {"symbol": sym})
            if signals:
                sig = max(signals, key=lambda x: x.confidence)
                s_cfg = config["symbols"][sym]
                ts, tv = float(s_cfg["point"]), float(s_cfg["contract_size"]) * float(s_cfg["point"])
                
                # --- CALL UNIFIED CALCULATE_LOT (Exactly like Live) ---
                lot = risk_manager.calculate_lot(sym, balance, 0, abs(sig.entry - sig.sl), ts, tv, sig.confidence)
                
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
                
                max_equity = max(max_equity, balance)
                dd = (max_equity - balance) / max_equity * 100
                max_dd = max(max_dd, dd)

    summary = {
        "initial_capital": initial_balance,
        "total_dca_added": total_dca,
        "final_equity": round(balance, 2),
        "total_profit": round(balance - (initial_balance + total_dca), 2),
        "max_drawdown": round(max_dd, 2),
        "total_trades": trades_count,
        "timestamp": datetime.now().isoformat()
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / f"dca_report_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print(f"🏁 FINISHED! FINAL EQUITY: ${balance:,.2f} | MaxDD: {max_dd:.1f}%")
    mt5.shutdown()

if __name__ == "__main__":
    run_dca_portfolio_backtest()
