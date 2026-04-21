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
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        
        # Split only on the first '='
        key, value = line.split("=", 1)
        key = key.strip()
        
        # If the key itself starts with #, it's a comment
        if key.startswith("#"):
            continue
            
        # Clean up quotes around the value
        value = value.strip().strip('"').strip("'")

        os.environ[key] = value

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MT5 backtests using live broker history")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--strategies", nargs="+", choices=["trend_following"], default=["trend_following"])
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def fetch_frame(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No H1 rates returned for {symbol}: {mt5.last_error()}")
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame.rename(columns={"tick_volume": "volume"}, inplace=True)
    return frame[["time", "open", "high", "low", "close", "volume"]]


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    login = int(require_env("MT5_LOGIN"))
    password = require_env("MT5_PASSWORD")
    server = require_env("MT5_SERVER")
    path = require_env("MT5_PATH")

    start = datetime.now(timezone.utc) - timedelta(days=args.days)
    end = datetime.now(timezone.utc)

    config = load_config(Path(args.config))
    logger = setup_logger("mt5_batch_backtest")
    strategy = build_strategy(config)

    if not mt5.initialize(path=path, login=login, password=password, server=server, timeout=60_000):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")

    reports_dir = ROOT / "reports"
    data_dir = ROOT / "data"
    reports_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not mt5.symbol_select(args.symbol, True):
            raise RuntimeError(f"Unable to select symbol {args.symbol}: {mt5.last_error()}")

        logger.info("Running trend_following on H1 for the last %s days", args.days)
        frame = fetch_frame(args.symbol, start, end)
        data_path = data_dir / f"real_{args.symbol.lower()}_h1_{args.days}d.csv"
        frame.to_csv(data_path, index=False)

        risk_manager = RiskManager(config["risk"], config["symbols"][args.symbol])
        backtester = Backtester(strategy, risk_manager, config, logger)
        result = backtester.run(frame, float(config["backtest"]["initial_balance"]), symbol=args.symbol)
        trades_path = reports_dir / f"trend_following_{args.days}d_trades.csv"
        backtester.export_trades(result["trades"], trades_path)
    finally:
        mt5.shutdown()

    payload: dict[str, Any] = {
        "strategy": "trend_following",
        "timeframe": "H1",
        "bars": len(frame),
        "start": frame["time"].min().isoformat(),
        "end": frame["time"].max().isoformat(),
        "total_trades": result["total_trades"],
        "net_profit": round(result["net_profit"], 2),
        "ending_balance": round(result["ending_balance"], 2),
        "max_drawdown_pct": round(result["max_drawdown_pct"], 2),
        "sharpe": round(result["sharpe"], 2),
        "win_rate": round(result["win_rate"], 2),
        "data_csv": str(data_path),
        "trades_csv": str(trades_path),
    }

    summary_path = reports_dir / f"mt5_backtest_summary_{args.days}d.json"
    summary_path.write_text(json.dumps([payload], indent=2), encoding="utf-8")
    print(json.dumps([payload], indent=2))
    print(f"\nSummary written to: {summary_path}")


if __name__ == "__main__":
    main()
