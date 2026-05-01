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

def run_dca_portfolio_backtest():
    # Parse CLI args
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3650)
    parser.add_argument("--balance", type=float, help="Initial balance (overrides config)")
    parser.add_argument("--dca", type=float, default=150.0, help="Monthly DCA amount in USD")
    args = parser.parse_args()

    config = load_dotenv_vars(load_config(ROOT / "config" / "config.yaml"))
    # DYNAMIC SYMBOLS: Read only what is defined in config
    symbols = list(config["symbols"].keys())
    
    if not mt5.initialize(
        path=config["mt5"]["path"],
        login=config["mt5"]["login"],
        password=os.getenv("MT5_PASSWORD"),
        server=config["mt5"]["server"]
    ):
        print(f"MT5 Init Failed")
        return

    # SET INITIAL BALANCE & DCA
    initial_balance = args.balance if args.balance else float(config.get("backtest", {}).get("initial_balance", 10000.0))
    balance = initial_balance
    monthly_dca_usd = args.dca
    total_dca_added = 0.0

    print(f"💰 STARTING TITAN DCA INFINITY BACKTEST")
    print(f"💵 Initial Capital: ${initial_balance:,.2f}")
    print(f"🏦 Monthly DCA:     ${monthly_dca_usd:,.2f}")
    print(f"📅 Duration:        {args.days} Days")
    print("-" * 40)
    
    # --- LOAD DATA ---
    data_map = {}
    for sym in symbols:
        print(f"📦 Fetching {sym}...")
        df = fetch_history(sym, args.days)
        if not df.empty:
            data_map[sym] = df
            print(f"✅ {sym} loaded.")

    if not data_map: 
        print("❌ Error: No data could be loaded. Check MT5 connection.")
        mt5.shutdown()
        return

    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = TrendFollowing(config["strategies"]["trend_following"])
    all_times = sorted(list(set(pd.concat([df["time"] for df in data_map.values()]))))
    
    trades_count = 0
    max_equity = balance
    max_dd = 0
    last_dca_month = -1
    
    print(f"🏃 Compounding with Monthly DCA of ${monthly_dca_usd}...")
    
    for i in range(1200, len(all_times) - 1):
        t = all_times[i]
        
        # --- DCA ACTION: Add funds on the 1st of every month ---
        if t.month != last_dca_month:
            balance += monthly_dca_usd
            total_dca_added += monthly_dca_usd
            last_dca_month = t.month
            max_equity = max(max_equity, balance)

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
                
                # USE % RISK FOR SUSTAINABLE DCA GROWTH (2.0%)
                lot = risk_manager.calculate_lot_percent(sym, balance, 2.0, abs(sig.entry - sig.sl), ts, tv)
                
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

        if i % 1000 == 0:
            print(f"📅 {t.strftime('%Y-%m')} | Equity: ${balance:,.2f} | MaxDD: {max_dd:.1f}%")

    # --- SAVE SUMMARY TO JSON WITH TIMESTAMP ---
    summary = {
        "initial_capital": initial_balance,
        "total_dca_added": total_dca_added,
        "final_equity": round(balance, 2),
        "total_profit": round(balance - (initial_balance + total_dca_added), 2),
        "roi_total_pct": round(((balance - initial_balance)/initial_balance)*100, 2),
        "max_drawdown": round(max_dd, 2),
        "total_trades": trades_count,
        "timestamp": datetime.now().isoformat()
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dca_report_{timestamp}.json"
    
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print(f"\n🏁 FINISHED! Results saved to reports/{filename}")
    print(f"💎 FINAL EQUITY: ${balance:,.2f}")
    
    mt5.shutdown()

def load_dotenv_vars(config):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    config["mt5"]["login"] = int(os.getenv("MT5_LOGIN", config["mt5"]["login"]))
    config["mt5"]["password"] = os.getenv("MT5_PASSWORD")
    config["mt5"]["server"] = os.getenv("MT5_SERVER", config["mt5"]["server"])
    return config

if __name__ == "__main__":
    run_dca_portfolio_backtest()
