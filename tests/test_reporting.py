from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.utils.reporting import PerformanceReporter


class ReportingTests(unittest.TestCase):
    def test_summarize_backtest_reads_csv(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report_path = root / "reports" / "report_test_trades.csv"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {"time": "2026-01-01T00:00:00+00:00", "strategy": "trend_following", "action": "BUY", "entry": 1, "exit": 2, "pnl": 10, "balance": 10010},
                {"time": "2026-01-01T01:00:00+00:00", "strategy": "trend_following", "action": "SELL", "entry": 2, "exit": 1, "pnl": -5, "balance": 10005},
            ]
        ).to_csv(report_path, index=False)
        reporter = PerformanceReporter()
        summary = reporter.summarize_backtest(report_path)
        self.assertIn("net_profit", summary)

    def test_summarize_log_reads_logfile(self) -> None:
        root = Path(__file__).resolve().parents[1]
        log_path = root / "logs" / "report_test.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "2026-01-01 | INFO | bot | Order sent:\n2026-01-01 | INFO | bot | Risk filter blocked\n",
            encoding="utf-8",
        )
        reporter = PerformanceReporter()
        summary = reporter.summarize_log(log_path)
        self.assertEqual(summary["orders_sent"], 1)
        self.assertEqual(summary["risk_blocks"], 1)


if __name__ == "__main__":
    unittest.main()
