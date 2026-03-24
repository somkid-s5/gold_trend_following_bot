from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


class PerformanceReporter:
    def summarize_backtest(self, trades_csv: str | Path) -> dict[str, Any]:
        frame = pd.read_csv(trades_csv)
        if frame.empty:
            return {
                "total_trades": 0,
                "net_profit": 0.0,
                "win_rate": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
            }
        pnl = frame["pnl"].astype(float)
        return {
            "total_trades": int(len(frame)),
            "net_profit": float(pnl.sum()),
            "win_rate": float((pnl > 0).mean() * 100),
            "best_trade": float(pnl.max()),
            "worst_trade": float(pnl.min()),
        }

    def summarize_log(self, log_path: str | Path) -> dict[str, Any]:
        path = Path(log_path)
        if not path.exists():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8")
        return {
            "orders_sent": len(re.findall(r"Order sent:", text)),
            "managed_positions": len(re.findall(r"managed", text)),
            "risk_blocks": len(re.findall(r"Risk filter blocked", text)),
            "live_errors": len(re.findall(r"Live loop error:", text)),
        }

    def render_text(self, summary: dict[str, Any], title: str) -> str:
        lines = [title]
        for key, value in summary.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
