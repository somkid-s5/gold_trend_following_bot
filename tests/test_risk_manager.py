from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.risk.risk_manager import RiskManager


class RiskManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = RiskManager(
            {
                "risk_per_trade_pct": 1.0,
                "max_daily_loss_pct": 3.0,
                "max_total_drawdown_pct": 12.0,
                "max_spread_points": 30,
                "breakeven_rr_trigger": 1.0,
                "trailing_stop_atr_multiple": 1.0,
            },
            {
                "point": 0.01,
                "contract_size": 100,
                "min_lot": 0.01,
                "max_lot": 20.0,
                "lot_step": 0.01,
            },
        )

    def test_calculate_lot_returns_positive_value(self) -> None:
        lot = self.manager.calculate_lot(equity=10_000, risk_pct=1.0, sl_distance_price=5.0)
        self.assertGreaterEqual(lot, 0.01)

    def test_drawdown_limit_blocks_after_loss(self) -> None:
        self.manager.update_equity_state(balance=10_000, equity=10_000)
        decision = self.manager.check_daily_dd(equity=9_650)
        self.assertFalse(decision.allowed)

    def test_news_filter_blocks_window(self) -> None:
        decision = self.manager.news_filter(
            datetime(2026, 3, 25, 12, 10, tzinfo=timezone.utc),
            {
                "enabled": True,
                "minutes_before": 45,
                "minutes_after": 30,
                "high_impact_events": ["2026-03-25T12:30:00+00:00"],
            },
        )
        self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()
