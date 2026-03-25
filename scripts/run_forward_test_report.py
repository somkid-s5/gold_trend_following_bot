from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a simple forward-test report from exported trade history")
    parser.add_argument("--trades-csv", required=True, help="CSV exported from MT5 account history or bot journal")
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args()


def max_consecutive_losses(pnl_series: pd.Series) -> int:
    max_streak = 0
    current = 0
    for pnl in pnl_series:
        if pnl < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    review_cfg = config.get("forward_test", {})

    frame = pd.read_csv(args.trades_csv)
    if frame.empty:
        raise SystemExit("Trades CSV is empty")

    if "time" not in frame.columns or "pnl" not in frame.columns:
        raise SystemExit("Trades CSV must contain at least 'time' and 'pnl' columns")

    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    if args.strategy and "strategy" in frame.columns:
        frame = frame.loc[frame["strategy"] == args.strategy].copy()
    if frame.empty:
        raise SystemExit("No trades matched the requested filter")

    frame["date"] = frame["time"].dt.date.astype(str)
    days_span = max(1, (frame["time"].max() - frame["time"].min()).days + 1)
    weekly_trade_rate = round((len(frame) / days_span) * 7, 2)
    daily = frame.groupby("date")["pnl"].sum().reset_index()

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": args.strategy or review_cfg.get("strategy", "unknown"),
        "review_time_utc": review_cfg.get("review_time_utc", "21:00"),
        "minimum_days": review_cfg.get("minimum_days", 14),
        "days_covered": days_span,
        "total_trades": int(len(frame)),
        "net_profit": round(float(frame["pnl"].sum()), 2),
        "average_trade": round(float(frame["pnl"].mean()), 2),
        "win_rate": round(float((frame["pnl"] > 0).mean() * 100), 2),
        "max_consecutive_losses": max_consecutive_losses(frame["pnl"]),
        "weekly_trade_rate": weekly_trade_rate,
        "target_trades_per_week": review_cfg.get("target_trades_per_week", 3),
        "best_trade": round(float(frame["pnl"].max()), 2),
        "worst_trade": round(float(frame["pnl"].min()), 2),
        "daily_pnl": daily.to_dict(orient="records"),
    }

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / "forward_test_report.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nForward test report written to: {output_path}")


if __name__ == "__main__":
    main()
