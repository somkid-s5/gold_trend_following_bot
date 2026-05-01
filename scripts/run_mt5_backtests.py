from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import build_strategy, load_config
from src.risk.risk_manager import RiskManager
from src.utils.backtester import Backtester
from src.utils.logger import setup_logger


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists(): return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line: continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("#"): continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value

def fetch_frame(symbol: str, start: datetime, end: datetime, mt5_timeframe: int) -> pd.DataFrame:
    rates = mt5.copy_rates_range(symbol, mt5_timeframe, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates returned for {symbol}: {mt5.last_error()}")
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame.rename(columns={"tick_volume": "volume"}, inplace=True)
    return frame[["time", "open", "high", "low", "close", "volume"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="TITAN Backtest Engine")
    parser.add_argument("--symbol", default="XAUUSDm")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = load_config(Path(args.config))
    logger = setup_logger("backtest_engine")
    strategy = build_strategy(config)
    
    tf_str = config["strategies"]["trend_following"].get("timeframe", "H1")
    mt5_tf = mt5.TIMEFRAME_H1 if tf_str == "H1" else mt5.TIMEFRAME_M15

    if not mt5.initialize(
        path=os.getenv("MT5_PATH"),
        login=int(os.getenv("MT5_LOGIN", 0)),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER")
    ):
        print(f"MT5 Init Failed: {mt5.last_error()}")
        return

    try:
        mt5.symbol_select(args.symbol, True)
        start = datetime.now(timezone.utc) - timedelta(days=args.days)
        end = datetime.now(timezone.utc)
        
        frame = fetch_frame(args.symbol, start, end, mt5_tf)
        risk_manager = RiskManager(config["risk"], config["symbols"])
        backtester = Backtester(strategy, risk_manager, config, logger)
        result = backtester.run(frame, float(config["backtest"]["initial_balance"]), symbol=args.symbol)
        
        # Save Report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        reports_dir = ROOT / "reports"
        reports_dir.mkdir(exist_ok=True)
        summary_path = reports_dir / f"backtest_{args.symbol}_{timestamp}.json"
        
        payload = {
            "symbol": args.symbol,
            "net_profit": round(result["net_profit"], 2),
            "roi_pct": round((result["net_profit"]/float(config["backtest"]["initial_balance"]))*100, 2),
            "max_drawdown": round(result["max_drawdown_pct"], 2),
            "total_trades": result["total_trades"],
            "win_rate": round(result["win_rate"], 2)
        }
        
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
            
        print(f"\n✅ DONE! Profit: ${payload['net_profit']} | ROI: {payload['roi_pct']}%")
        print(f"📄 Report: reports/{summary_path.name}")

    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
