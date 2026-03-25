from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(slots=True)
class GuardStatus:
    status: str
    reasons: list[str]
    metrics: dict[str, Any]


def max_consecutive_losses(pnl_values: list[float]) -> int:
    max_streak = 0
    current = 0
    for pnl in pnl_values:
        if pnl < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


class OperationalGuardEvaluator:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def evaluate_trade_frame(self, frame: pd.DataFrame) -> GuardStatus:
        if frame.empty:
            return GuardStatus("OK", ["No trades available yet"], {"total_trades": 0})

        window = int(self.config.get("evaluation_window", len(frame)))
        window_frame = frame.tail(window).copy()
        pnl = window_frame["pnl"].astype(float)
        if "balance" in window_frame.columns:
            equity_curve = window_frame["balance"].astype(float)
            peak = equity_curve.cummax()
            drawdown_pct = (((peak - equity_curve) / peak.replace(0, pd.NA)) * 100).max()
            drawdown_pct = 0.0 if pd.isna(drawdown_pct) else float(drawdown_pct)
        else:
            equity_curve = pnl.cumsum()
            peak = equity_curve.cummax()
            absolute_drawdown = (peak - equity_curve).max() if not equity_curve.empty else 0.0
            baseline = max(1.0, abs(float(peak.max())) if not peak.empty else 1.0)
            drawdown_pct = float((absolute_drawdown / baseline) * 100)
        gross_profit = pnl[pnl > 0].sum()
        gross_loss = -pnl[pnl < 0].sum()
        win_rate = float((pnl > 0).mean() * 100) if len(window_frame) else 0.0
        consecutive_losses = max_consecutive_losses(pnl.tolist())

        metrics = {
            "total_trades": int(len(frame)),
            "window_trades": int(len(window_frame)),
            "net_profit_window": round(float(pnl.sum()), 2),
            "max_drawdown_pct_window": round(drawdown_pct, 2),
            "win_rate_window": round(win_rate, 2),
            "gross_profit_window": round(float(gross_profit), 2),
            "gross_loss_window": round(float(gross_loss), 2),
            "max_consecutive_losses": consecutive_losses,
        }

        reasons: list[str] = []
        if len(frame) < int(self.config.get("minimum_trades", 20)):
            reasons.append("Not enough trades collected for guard enforcement")
            return GuardStatus("OK", reasons, metrics)

        if consecutive_losses >= int(self.config.get("max_consecutive_losses", 6)):
            reasons.append(
                f"Max consecutive losses reached: {consecutive_losses} >= {self.config.get('max_consecutive_losses', 6)}"
            )
        if drawdown_pct >= float(self.config.get("max_drawdown_pct", 5.0)):
            reasons.append(
                f"Rolling drawdown too high: {drawdown_pct:.2f}% >= {float(self.config.get('max_drawdown_pct', 5.0)):.2f}%"
            )
        if win_rate < float(self.config.get("min_win_rate_pct", 45.0)):
            reasons.append(
                f"Rolling win rate too low: {win_rate:.2f}% < {float(self.config.get('min_win_rate_pct', 45.0)):.2f}%"
            )

        status = "PAUSE" if reasons else "OK"
        if not reasons:
            reasons.append("All operational guard checks passed")
        return GuardStatus(status, reasons, metrics)

    def evaluate_trade_csv(self, csv_path: str | Path) -> GuardStatus:
        frame = pd.read_csv(csv_path)
        if "pnl" not in frame.columns:
            raise ValueError("Trades CSV must include a 'pnl' column")
        return self.evaluate_trade_frame(frame)

    def load_guard_file(self, path: str | Path) -> GuardStatus | None:
        report_path = Path(path)
        if not report_path.exists():
            return None
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return GuardStatus(
            status=str(payload.get("status", "OK")),
            reasons=list(payload.get("reasons", [])),
            metrics=dict(payload.get("metrics", {})),
        )
