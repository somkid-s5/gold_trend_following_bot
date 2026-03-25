from __future__ import annotations

import unittest

import pandas as pd

from src.core.operational_guards import OperationalGuardEvaluator


class OperationalGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = OperationalGuardEvaluator(
            {
                "evaluation_window": 10,
                "minimum_trades": 5,
                "max_consecutive_losses": 3,
                "max_drawdown_pct": 50.0,
                "min_win_rate_pct": 45.0,
            }
        )

    def test_guard_pauses_on_loss_streak(self) -> None:
        frame = pd.DataFrame({"pnl": [10, -5, -6, -7, -8, 12]})
        status = self.evaluator.evaluate_trade_frame(frame)
        self.assertEqual(status.status, "PAUSE")
        self.assertTrue(any("consecutive losses" in reason.lower() for reason in status.reasons))

    def test_guard_ok_when_metrics_are_healthy(self) -> None:
        frame = pd.DataFrame({"pnl": [10, -2, 8, 5, -1, 7]})
        status = self.evaluator.evaluate_trade_frame(frame)
        self.assertEqual(status.status, "OK")


if __name__ == "__main__":
    unittest.main()
