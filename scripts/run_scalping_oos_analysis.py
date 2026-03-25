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

from main import load_config
from src.risk.risk_manager import RiskManager
from src.strategies.scalping_smc import ScalpingSMC
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
    parser = argparse.ArgumentParser(description="Run in-sample/out-of-sample analysis for scalping_smc")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--split-ratio", type=float, default=0.7, help="Fraction used for in-sample period")
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args()


def fetch_frame(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No M5 rates returned for {symbol}: {mt5.last_error()}")
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


def trade_profit_factor(trades: list[dict[str, Any]]) -> float:
    if not trades:
        return 0.0
    frame = pd.DataFrame(trades)
    gross_profit = frame.loc[frame["pnl"] > 0, "pnl"].sum()
    gross_loss = -frame.loc[frame["pnl"] < 0, "pnl"].sum()
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return float(gross_profit / gross_loss)


def action_breakdown(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not trades:
        return []
    frame = pd.DataFrame(trades)
    grouped = frame.groupby("action")["pnl"].agg(["count", "sum", "mean"]).reset_index()
    grouped.rename(columns={"count": "trades", "sum": "net_profit", "mean": "avg_pnl"}, inplace=True)
    return grouped.to_dict(orient="records")


def average_trades_per_day(frame: pd.DataFrame, trades: list[dict[str, Any]]) -> float:
    if frame.empty:
        return 0.0
    period_days = max((frame["time"].max() - frame["time"].min()).total_seconds() / 86400, 1.0)
    return round(len(trades) / period_days, 2)


def run_backtest(frame: pd.DataFrame, config: dict[str, Any], logger_name: str) -> dict[str, Any]:
    logger = setup_logger(logger_name)
    strategy = ScalpingSMC(
        config["strategies"]["scalping_smc"],
        config["sessions"]["london_ny_overlap"],
    )
    risk_manager = RiskManager(config["risk"], config["symbols"]["XAUUSD"])
    backtester = Backtester(strategy, risk_manager, config, logger)
    result = backtester.run(frame, float(config["backtest"]["initial_balance"]))
    result["profit_factor"] = trade_profit_factor(result["trade_records"])
    result["action_breakdown"] = action_breakdown(result["trade_records"])
    result["avg_trades_per_day"] = average_trades_per_day(frame, result["trade_records"])
    return result


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
    logger = setup_logger("scalping_oos_analysis")

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

    in_result = run_backtest(in_sample, config, "scalping_oos_in_sample")
    out_result = run_backtest(out_of_sample, config, "scalping_oos_out_sample")

    payload = {
        "strategy": "scalping_smc",
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
            "profit_factor": round(in_result["profit_factor"], 2) if in_result["profit_factor"] != float("inf") else "inf",
            "avg_trades_per_day": in_result["avg_trades_per_day"],
            "action_breakdown": in_result["action_breakdown"],
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
            "profit_factor": round(out_result["profit_factor"], 2) if out_result["profit_factor"] != float("inf") else "inf",
            "avg_trades_per_day": out_result["avg_trades_per_day"],
            "action_breakdown": out_result["action_breakdown"],
            "monthly": summarize_monthly(out_result["trade_records"]),
        },
    }

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"scalping_smc_oos_{args.days}d.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("OOS analysis written to %s", output_path)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
