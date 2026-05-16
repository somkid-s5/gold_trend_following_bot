from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False
    mt5 = None

import pandas as pd

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import build_strategy, load_config, load_dotenv
from src.risk.risk_manager import RiskManager
from src.utils.backtester import Backtester
from src.utils.logger import setup_logger

# Map MT5 symbols to Yahoo Finance symbols
SYMBOL_MAP = {
    "XAUUSDm": "XAUUSD=X",
    "XAUUSD": "XAUUSD=X",
    "GOLD": "XAUUSD=X"
}

def fetch_history(symbol: str, days: int, logger: Any = None) -> pd.DataFrame:
    if HAS_MT5 and mt5.terminal_info() is not None:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            if "tick_volume" in df.columns:
                df.rename(columns={"tick_volume": "volume"}, inplace=True)
            return df
    
    # Fallback to Yahoo Finance
    if HAS_YF:
        yf_sym = SYMBOL_MAP.get(symbol, symbol)
        if logger: logger.info("MT5 unavailable. Falling back to Yahoo Finance for %s (%s)", symbol, yf_sym)
        
        # yfinance fetch
        ticker = yf.Ticker(yf_sym)
        # interval '1h' for H1
        period = f"{days}d" if days <= 730 else "max"
        df = ticker.history(period=period, interval="1h")
        
        if df.empty:
            return pd.DataFrame()
            
        df = df.reset_index()
        df.rename(columns={
            "Datetime": "time",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        }, inplace=True)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        return df
        
    return pd.DataFrame()


def run_standard_backtest(args: argparse.Namespace, config: dict[str, Any], logger: Any) -> dict[str, Any]:
    symbol = args.symbol
    days = args.days
    
    if HAS_MT5 and mt5.terminal_info() is not None:
        if not mt5.symbol_select(symbol, True):
            logger.warning(f"Unable to select symbol {symbol} in MT5: {mt5.last_error()}")
    
    logger.info("Running Standard Backtest for %s (%s days)", symbol, days)
    frame = fetch_history(symbol, days, logger)
    if frame.empty:
        raise RuntimeError(f"No history data for {symbol}")

    strategy = build_strategy(config)
    risk_manager = RiskManager(config["risk"], config["symbols"][symbol])
    backtester = Backtester(strategy, risk_manager, config, logger)
    
    initial_balance = args.balance or float(config["backtest"]["initial_balance"])
    result = backtester.run(frame, initial_balance, symbol=symbol)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    trades_path = reports_dir / f"trades_{symbol}_{timestamp}.csv"
    backtester.export_trades(result["trades"], trades_path)
    
    payload = {
        "symbol": symbol,
        "strategy": "trend_following",
        "net_profit": round(result["net_profit"], 2),
        "roi_pct": round((result["net_profit"] / initial_balance) * 100, 2),
        "max_drawdown": round(result["max_drawdown_pct"], 2),
        "total_trades": result["total_trades"],
        "win_rate": round(result["win_rate"], 2),
        "final_equity": round(result["ending_balance"], 2),
        "timestamp": datetime.now().isoformat()
    }
    
    report_path = reports_dir / f"backtest_{symbol}_{timestamp}.json"
    report_path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    return payload


def run_dca_backtest(args: argparse.Namespace, config: dict[str, Any], logger: Any) -> dict[str, Any]:
    days = args.days
    initial_balance = args.balance or 10000.0
    dca_amount = args.dca or 150.0
    symbols = list(config["symbols"].keys())
    
    logger.info("Running Unified DCA Backtest (%s days, $%s initial, $%s monthly DCA)", days, initial_balance, dca_amount)
    
    data_map = {}
    for sym in symbols:
        df = fetch_history(sym, days, logger)
        if not df.empty:
            data_map[sym] = df

    if not data_map:
        raise RuntimeError("No history data found for any symbols")

    balance = initial_balance
    total_dca = 0.0
    risk_manager = RiskManager(config["risk"], config["symbols"])
    strategy = build_strategy(config)
    
    # Combine all unique timestamps
    all_times = sorted(list(set(pd.concat([df["time"] for df in data_map.values()]))))
    
    last_month = -1
    trades_count = 0
    wins = 0
    max_equity = balance
    max_dd = 0

    # Start after some warmup (approx 50 days of H1 bars)
    start_idx = min(1200, len(all_times) - 1)
    
    for i in range(start_idx, len(all_times) - 1):
        t = all_times[i]
        
        # Monthly DCA
        if t.month != last_month:
            if last_month != -1: # Don't add on first bar
                balance += dca_amount
                total_dca += dca_amount
            last_month = t.month

        risk_manager.update_equity_state(balance, balance)
        
        for sym, df in data_map.items():
            # Find matching bar for this timestamp
            match = df[df["time"] == t]
            if match.empty: continue
            
            idx = match.index[0]
            if idx < 100 or idx + 1 >= len(df): continue
            
            signals = strategy.generate_signals(df.iloc[idx-100:idx+1], {"symbol": sym})
            if signals:
                sig = max(signals, key=lambda x: x.confidence)
                s_cfg = config["symbols"][sym]
                ts = float(s_cfg["point"])
                tv = float(s_cfg["contract_size"]) * ts
                
                lot = risk_manager.calculate_lot(sym, balance, args.risk or 2.0, abs(sig.entry - sig.sl), ts, tv, sig.confidence)
                
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
                if pnl > 0: wins += 1
                
                max_equity = max(max_equity, balance)
                dd = (max_equity - balance) / max_equity * 100
                max_dd = max(max_dd, dd)

    payload = {
        "symbol": "Portfolio (DCA)",
        "initial_capital": initial_balance,
        "total_dca_added": total_dca,
        "final_equity": round(balance, 2),
        "net_profit": round(balance - (initial_balance + total_dca), 2),
        "roi_pct": round((round(balance - (initial_balance + total_dca), 2) / (initial_balance + total_dca)) * 100, 2),
        "max_drawdown": round(max_dd, 2),
        "total_trades": trades_count,
        "win_rate": round((wins / trades_count * 100) if trades_count > 0 else 0, 2),
        "timestamp": datetime.now().isoformat()
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"dca_report_{timestamp}.json"
    report_path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="TITAN Unified Backtest Runner")
    parser.add_argument("--type", choices=["standard", "dca"], default="standard")
    parser.add_argument("--symbol", default="XAUUSDm")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--balance", type=float)
    parser.add_argument("--dca", type=float, help="Monthly DCA amount (for dca type)")
    parser.add_argument("--risk", type=float, help="Risk per trade %")
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = load_config(Path(args.config))
    logger = setup_logger("backtest_runner")

    # Override config with args if provided
    if args.risk:
        config["risk"]["risk_per_trade_pct"] = args.risk

    if HAS_MT5:
        # MT5 connection
        login_env = os.getenv("MT5_LOGIN")
        login = int(login_env) if login_env and login_env.isdigit() else 0
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        path = os.getenv("MT5_PATH")

        if login > 0 and mt5.initialize(path=path, login=login, password=password, server=server, timeout=60_000):
            logger.info("MT5 initialized successfully")
        else:
            logger.warning("MT5 initialize failed or no credentials: %s. Using fallback data if available.", mt5.last_error() if HAS_MT5 else "MT5 not installed")
    else:
        logger.info("Running in non-MT5 mode (Docker/Linux). Will use Yahoo Finance fallback.")

    try:
        if args.type == "dca":
            result = run_dca_backtest(args, config, logger)
        else:
            result = run_standard_backtest(args, config, logger)
        
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.exception("Backtest failed: %s", e)
        sys.exit(1)
    finally:
        if HAS_MT5:
            mt5.shutdown()


if __name__ == "__main__":
    main()
