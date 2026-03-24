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

from main import build_strategies, load_config
from src.risk.risk_manager import RiskManager
from src.utils.backtester import Backtester
from src.utils.logger import setup_logger


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run in-sample/out-of-sample analysis for trend_following")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--split-ratio", type=float, default=0.7, help="Fraction used for in-sample period")
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args()


def fetch_frame(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No H1 rates returned for {symbol}: {mt5.last_error()}")
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame.rename(columns={"tick_volume": "volume"}, inplace=True)
    return frame[["time", "open", "high", "low", "close", "volume"]]


def summarize_monthly(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not trades:
        return []
    frame = pd.DataFrame(trades)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame["month"] = frame["time"].dt.to_period("M").astype(str)
    grouped = frame.groupby("month")["pnl"].agg(["count", "sum"]).reset_index()
    return grouped.to_dict(orient="records")


def run_backtest(frame: pd.DataFrame, config: dict[str, Any], logger_name: str) -> dict[str, Any]:
    logger = setup_logger(logger_name)
    strategy = build_strategies(config)["trend_following"]
    risk_manager = RiskManager(config["risk"], config["symbols"]["XAUUSD"])
    backtester = Backtester(strategy, risk_manager, config, logger)
    return backtester.run(frame, float(config["backtest"]["initial_balance"]))


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
    logger = setup_logger("trend_oos_analysis")

    if not mt5.initialize(path=path, login=login, password=password, server=server, timeout=60_000):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")

    try:
        if not mt5.symbol_select(args.symbol, True):
            raise RuntimeError(f"Unable to select symbol {args.symbol}: {mt5.last_error()}")
        frame = fetch_frame(args.symbol, start, end)
    finally:
        mt5.shutdown()

    split_index = int(len(frame) * args.split_ratio)
    in_sample = frame.iloc[:split_index].reset_index(drop=True)
    out_of_sample = frame.iloc[split_index:].reset_index(drop=True)

    in_result = run_backtest(in_sample, config, "trend_oos_in_sample")
    out_result = run_backtest(out_of_sample, config, "trend_oos_out_sample")

    payload = {
        "strategy": "trend_following",
        "days": args.days,
        "split_ratio": args.split_ratio,
        "in_sample": {
            "bars": len(in_sample),
            "start": in_sample["time"].min().isoformat(),
            "end": in_sample["time"].max().isoformat(),
            "total_trades": in_result["total_trades"],
            "net_profit": round(in_result["net_profit"], 2),
            "ending_balance": round(in_result["ending_balance"], 2),
            "max_drawdown_pct": round(in_result["max_drawdown_pct"], 2),
            "sharpe": round(in_result["sharpe"], 2),
            "win_rate": round(in_result["win_rate"], 2),
            "monthly": summarize_monthly(in_result["trade_records"]),
        },
        "out_of_sample": {
            "bars": len(out_of_sample),
            "start": out_of_sample["time"].min().isoformat(),
            "end": out_of_sample["time"].max().isoformat(),
            "total_trades": out_result["total_trades"],
            "net_profit": round(out_result["net_profit"], 2),
            "ending_balance": round(out_result["ending_balance"], 2),
            "max_drawdown_pct": round(out_result["max_drawdown_pct"], 2),
            "sharpe": round(out_result["sharpe"], 2),
            "win_rate": round(out_result["win_rate"], 2),
            "monthly": summarize_monthly(out_result["trade_records"]),
        },
    }

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"trend_following_oos_{args.days}d.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("OOS analysis written to %s", output_path)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
