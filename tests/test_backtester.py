from __future__ import annotations

import unittest
from pathlib import Path

from src.data.data_handler import DataHandler
from src.risk.risk_manager import RiskManager
from src.strategies.trend_following import TrendFollowing
from src.utils.backtester import Backtester
from src.utils.logger import setup_logger


class BacktesterTests(unittest.TestCase):
    def test_backtester_runs_on_sample_csv(self) -> None:
        root = Path(__file__).resolve().parents[1]
        frame = DataHandler().load_csv(root / "data" / "xauusd_h1.csv")
        config = {
            "risk": {
                "risk_per_trade_pct": 1.0,
                "max_daily_loss_pct": 3.0,
                "max_total_drawdown_pct": 12.0,
                "max_spread_points": 30,
                "breakeven_rr_trigger": 1.0,
                "trailing_stop_atr_multiple": 1.0,
            },
            "symbols": {
                "XAUUSD": {
                    "point": 0.01,
                    "contract_size": 100,
                    "min_lot": 0.01,
                    "max_lot": 20.0,
                    "lot_step": 0.01,
                }
            },
            "backtest": {
                "fee_per_lot": 7.0,
            },
        }
        strategy = TrendFollowing(
            {
                "timeframe": "H1",
                "fast_ema": 50,
                "slow_ema": 200,
                "rsi_period": 14,
                "rsi_buy_level": 40,
                "rsi_sell_level": 60,
                "atr_period": 14,
                "atr_sl_multiplier": 1.5,
                "take_profit_rr": 2.0,
            }
        )
        risk_manager = RiskManager(config["risk"], config["symbols"]["XAUUSD"])
        backtester = Backtester(strategy, risk_manager, config, setup_logger("test_backtester"))
        results = backtester.run(frame, 10_000.0)
        self.assertIn("net_profit", results)
        self.assertIn("sharpe", results)
        self.assertGreaterEqual(results["total_trades"], 0)


if __name__ == "__main__":
    unittest.main()
