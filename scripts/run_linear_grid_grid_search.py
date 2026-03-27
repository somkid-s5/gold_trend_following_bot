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
from src.strategies.linear_grid import LinearGrid
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


def parse_bool_list(raw: str) -> list[bool]:
    return [item.strip().lower() == "true" for item in raw.split(",") if item.strip()]


def parse_text_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grid search linear_grid on MT5 history")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--split-ratio", type=float, default=0.7)
    parser.add_argument("--data-csv", default=None, help="Optional cached H4 CSV to skip MT5 download")
    parser.add_argument("--spacing-multipliers", default="0.6,0.8,1.0")
    parser.add_argument("--tp-multipliers", default="1.0,1.2,1.5")
    parser.add_argument("--zone-lookbacks", default="20,30,40")
    parser.add_argument("--zone-buffer-atrs", default="0.0,0.2,0.4")
    parser.add_argument("--trend-fast-emas", default="21,34")
    parser.add_argument("--trend-slow-emas", default="55,89")
    parser.add_argument("--trend-alignment-values", default="true,false")
    parser.add_argument("--trade-modes", default="buy_only,both")
    parser.add_argument("--max-positions-values", default="2,3")
    parser.add_argument("--max-combos", type=int, default=0)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args()


def fetch_frame(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H4, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No H4 rates returned for {symbol}: {mt5.last_error()}")
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame.rename(columns={"tick_volume": "volume"}, inplace=True)
    return frame[["time", "open", "high", "low", "close", "volume"]]


def load_cached_frame(csv_path: str | Path, days: int | None = None) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame[["time", "open", "high", "low", "close", "volume"]]
    if days and not frame.empty:
        end_time = frame["time"].max()
        start_time = end_time - timedelta(days=days)
        frame = frame.loc[frame["time"] >= start_time].reset_index(drop=True)
    return frame


def trade_profit_factor(trades: list[dict[str, Any]]) -> float:
    if not trades:
        return 0.0
    frame = pd.DataFrame(trades)
    gross_profit = frame.loc[frame["pnl"] > 0, "pnl"].sum()
    gross_loss = -frame.loc[frame["pnl"] < 0, "pnl"].sum()
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return float(gross_profit / gross_loss)


def action_breakdown(trades: list[dict[str, Any]]) -> dict[str, float]:
    if not trades:
        return {"buy_net": 0.0, "sell_net": 0.0}
    frame = pd.DataFrame(trades)
    buy_net = float(frame.loc[frame["action"] == "BUY", "pnl"].sum())
    sell_net = float(frame.loc[frame["action"] == "SELL", "pnl"].sum())
    return {"buy_net": round(buy_net, 2), "sell_net": round(sell_net, 2)}


def apply_trade_mode(strategy_config: dict[str, Any], trade_mode: str) -> None:
    strategy_config["allow_long"] = trade_mode in {"both", "buy_only"}
    strategy_config["allow_short"] = trade_mode in {"both", "sell_only"}


def run_backtest(frame: pd.DataFrame, config: dict[str, Any], strategy_config: dict[str, Any], logger_name: str) -> dict[str, Any]:
    logger = setup_logger(logger_name)
    risk_manager = RiskManager(config["risk"], config["symbols"]["XAUUSD"])
    backtester = Backtester(LinearGrid(strategy_config), risk_manager, config, logger)
    result = backtester.run(frame, float(config["backtest"]["initial_balance"]))
    result["profit_factor"] = trade_profit_factor(result["trade_records"])
    result["action_breakdown"] = action_breakdown(result["trade_records"])
    return result


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")

    start = datetime.now(timezone.utc) - timedelta(days=args.days)
    end = datetime.now(timezone.utc)

    config = load_config(Path(args.config))
    logger = setup_logger("linear_grid_grid_search")

    if args.data_csv:
        frame = load_cached_frame(args.data_csv, args.days)
        logger.info("Loaded cached data from %s", args.data_csv)
    else:
        login = int(require_env("MT5_LOGIN"))
        password = require_env("MT5_PASSWORD")
        server = require_env("MT5_SERVER")
        path = require_env("MT5_PATH")

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

    spacing_multipliers = parse_list(args.spacing_multipliers)
    tp_multipliers = parse_list(args.tp_multipliers)
    zone_lookbacks = [int(value) for value in parse_list(args.zone_lookbacks)]
    zone_buffer_atrs = parse_list(args.zone_buffer_atrs)
    trend_fast_emas = [int(value) for value in parse_list(args.trend_fast_emas)]
    trend_slow_emas = [int(value) for value in parse_list(args.trend_slow_emas)]
    trend_alignment_values = parse_bool_list(args.trend_alignment_values)
    trade_modes = parse_text_list(args.trade_modes)
    max_positions_values = [int(value) for value in parse_list(args.max_positions_values)]

    combinations = list(
        itertools.product(
            spacing_multipliers,
            tp_multipliers,
            zone_lookbacks,
            zone_buffer_atrs,
            trend_fast_emas,
            trend_slow_emas,
            trend_alignment_values,
            trade_modes,
            max_positions_values,
        )
    )
    if args.max_combos > 0:
        combinations = combinations[: args.max_combos]

    results: list[dict[str, Any]] = []
    for index, (
        spacing_multiplier,
        tp_multiplier,
        zone_lookback,
        zone_buffer_atr,
        trend_fast_ema,
        trend_slow_ema,
        trend_alignment,
        trade_mode,
        max_positions,
    ) in enumerate(combinations, start=1):
        if trend_fast_ema >= trend_slow_ema:
            continue

        strategy_config = deepcopy(config["strategies"]["linear_grid"])
        strategy_config.update(
            {
                "spacing_atr_multiplier": spacing_multiplier,
                "take_profit_atr_multiplier": tp_multiplier,
                "zone_lookback": zone_lookback,
                "zone_buffer_atr": zone_buffer_atr,
                "trend_fast_ema": trend_fast_ema,
                "trend_slow_ema": trend_slow_ema,
                "require_trend_alignment": trend_alignment,
                "max_positions": max_positions,
            }
        )
        apply_trade_mode(strategy_config, trade_mode)

        in_result = run_backtest(in_sample, config, strategy_config, "linear_grid_in_sample")
        out_result = run_backtest(out_of_sample, config, strategy_config, "linear_grid_out_sample")

        in_pf = in_result["profit_factor"]
        out_pf = out_result["profit_factor"]
        row = {
            "spacing_atr_multiplier": spacing_multiplier,
            "take_profit_atr_multiplier": tp_multiplier,
            "zone_lookback": zone_lookback,
            "zone_buffer_atr": zone_buffer_atr,
            "trend_fast_ema": trend_fast_ema,
            "trend_slow_ema": trend_slow_ema,
            "require_trend_alignment": trend_alignment,
            "trade_mode": trade_mode,
            "max_positions": max_positions,
            "in_net_profit": round(in_result["net_profit"], 2),
            "in_sharpe": round(in_result["sharpe"], 2),
            "in_profit_factor": round(in_pf, 2) if in_pf != float("inf") else "inf",
            "in_max_dd": round(in_result["max_drawdown_pct"], 2),
            "out_net_profit": round(out_result["net_profit"], 2),
            "out_sharpe": round(out_result["sharpe"], 2),
            "out_profit_factor": round(out_pf, 2) if out_pf != float("inf") else "inf",
            "out_max_dd": round(out_result["max_drawdown_pct"], 2),
            "out_win_rate": round(out_result["win_rate"], 2),
            "buy_net_out": out_result["action_breakdown"]["buy_net"],
            "sell_net_out": out_result["action_breakdown"]["sell_net"],
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
    output_path = reports_dir / f"linear_grid_grid_search_{args.days}d.json"
    output_path.write_text(json.dumps(top_results, indent=2), encoding="utf-8")
    print(json.dumps(top_results, indent=2))
    print(f"\nTop results written to: {output_path}")


if __name__ == "__main__":
    main()
