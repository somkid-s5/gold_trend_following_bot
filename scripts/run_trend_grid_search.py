from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from copy import deepcopy
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
from src.strategies.trend_following import TrendFollowing
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


def parse_list(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grid search trend_following on MT5 history")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--split-ratio", type=float, default=0.7)
    parser.add_argument("--fast-emas", default="34,50,72")
    parser.add_argument("--slow-emas", default="150,200,250")
    parser.add_argument("--buy-levels", default="35,40,45")
    parser.add_argument("--sell-levels", default="55,60,65")
    parser.add_argument("--atr-multipliers", default="1.2,1.5,1.8")
    parser.add_argument("--rr-values", default="1.5,2.0,2.5")
    parser.add_argument("--top", type=int, default=10)
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


def trade_profit_factor(trades: list[dict[str, Any]]) -> float:
    if not trades:
        return 0.0
    frame = pd.DataFrame(trades)
    gross_profit = frame.loc[frame["pnl"] > 0, "pnl"].sum()
    gross_loss = -frame.loc[frame["pnl"] < 0, "pnl"].sum()
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return float(gross_profit / gross_loss)


def run_backtest(frame: pd.DataFrame, config: dict[str, Any], strategy_config: dict[str, Any], logger_name: str) -> dict[str, Any]:
    logger = setup_logger(logger_name)
    risk_manager = RiskManager(config["risk"], config["symbols"]["XAUUSD"])
    backtester = Backtester(TrendFollowing(strategy_config), risk_manager, config, logger)
    result = backtester.run(frame, float(config["backtest"]["initial_balance"]))
    result["profit_factor"] = trade_profit_factor(result["trade_records"])
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
    logger = setup_logger("trend_grid_search")

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

    fast_emas = [int(value) for value in parse_list(args.fast_emas)]
    slow_emas = [int(value) for value in parse_list(args.slow_emas)]
    buy_levels = parse_list(args.buy_levels)
    sell_levels = parse_list(args.sell_levels)
    atr_multipliers = parse_list(args.atr_multipliers)
    rr_values = parse_list(args.rr_values)

    combinations = list(itertools.product(fast_emas, slow_emas, buy_levels, sell_levels, atr_multipliers, rr_values))
    results: list[dict[str, Any]] = []

    for index, (fast_ema, slow_ema, buy_level, sell_level, atr_multiplier, rr_value) in enumerate(combinations, start=1):
        if fast_ema >= slow_ema:
            continue
        strategy_config = deepcopy(config["strategies"]["trend_following"])
        strategy_config.update(
            {
                "fast_ema": fast_ema,
                "slow_ema": slow_ema,
                "rsi_buy_level": buy_level,
                "rsi_sell_level": sell_level,
                "atr_sl_multiplier": atr_multiplier,
                "take_profit_rr": rr_value,
            }
        )

        in_result = run_backtest(in_sample, config, strategy_config, "trend_grid_in_sample")
        out_result = run_backtest(out_of_sample, config, strategy_config, "trend_grid_out_sample")
        row = {
            "fast_ema": fast_ema,
            "slow_ema": slow_ema,
            "rsi_buy_level": buy_level,
            "rsi_sell_level": sell_level,
            "atr_sl_multiplier": atr_multiplier,
            "take_profit_rr": rr_value,
            "in_net_profit": round(in_result["net_profit"], 2),
            "in_sharpe": round(in_result["sharpe"], 2),
            "in_profit_factor": round(in_result["profit_factor"], 2) if in_result["profit_factor"] != float("inf") else "inf",
            "in_max_dd": round(in_result["max_drawdown_pct"], 2),
            "out_net_profit": round(out_result["net_profit"], 2),
            "out_sharpe": round(out_result["sharpe"], 2),
            "out_profit_factor": round(out_result["profit_factor"], 2) if out_result["profit_factor"] != float("inf") else "inf",
            "out_max_dd": round(out_result["max_drawdown_pct"], 2),
            "out_win_rate": round(out_result["win_rate"], 2),
            "score": round(out_result["net_profit"] - (out_result["max_drawdown_pct"] * 10), 2),
        }
        results.append(row)
        logger.info("Checked %s/%s combos: %s", index, len(combinations), row)

    ranked = sorted(
        results,
        key=lambda item: (item["score"], item["out_profit_factor"] if item["out_profit_factor"] != "inf" else 999),
        reverse=True,
    )
    top_results = ranked[: args.top]

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"trend_following_grid_search_{args.days}d.json"
    output_path.write_text(json.dumps(top_results, indent=2), encoding="utf-8")
    print(json.dumps(top_results, indent=2))
    print(f"\nTop results written to: {output_path}")


if __name__ == "__main__":
    main()
