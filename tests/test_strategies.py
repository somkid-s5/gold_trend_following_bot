from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.strategies.linear_grid import LinearGrid
from src.strategies.scalping_smc import ScalpingSMC
from src.strategies.trend_following import TrendFollowing


def build_frame(closes: list[float], volume_base: int = 1500) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    previous = closes[0]
    for index, close in enumerate(closes):
        open_price = previous
        high = max(open_price, close) + 0.8
        low = min(open_price, close) - 0.8
        rows.append(
            {
                "time": start + timedelta(minutes=5 * index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume_base + (index % 20) * 40,
            }
        )
        previous = close
    return pd.DataFrame(rows)


class StrategyTests(unittest.TestCase):
    def test_trend_following_generates_buy_signal(self) -> None:
        closes = [1800 + i * 0.6 for i in range(205)] + [1918, 1912, 1908, 1904, 1912]
        frame = build_frame(closes)
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
        signals = strategy.generate_signals(frame)
        self.assertTrue(any(signal.action == "BUY" for signal in signals))

    def test_linear_grid_generates_signal_near_zone(self) -> None:
        closes = [2500 + (i % 5) * 0.5 for i in range(50)] + [2492.0]
        frame = build_frame(closes)
        strategy = LinearGrid(
            {
                "timeframe": "H4",
                "atr_period": 14,
                "grid_levels": 3,
                "spacing_atr_multiplier": 0.8,
                "zone_lookback": 30,
                "take_profit_atr_multiplier": 1.2,
                "max_positions": 3,
            }
        )
        signals = strategy.generate_signals(frame, {"existing_positions": 0, "daily_drawdown_pct": 0.0, "max_daily_loss_pct": 3.0})
        self.assertGreaterEqual(len(signals), 1)

    def test_scalping_smc_returns_list(self) -> None:
        closes = [2600 + i * 0.03 for i in range(120)]
        frame = build_frame(closes, volume_base=2000)
        frame["time"] = pd.date_range("2026-01-01 12:00:00+00:00", periods=len(frame), freq="5min")
        strategy = ScalpingSMC(
            {
                "timeframe": "M5",
                "bb_period": 20,
                "bb_std": 2.0,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "volume_window": 20,
                "atr_period": 14,
                "atr_sl_multiplier": 1.2,
                "take_profit_rr": 1.5,
            },
            {"start_utc": "12:00", "end_utc": "16:00"},
        )
        signals = strategy.generate_signals(frame)
        self.assertIsInstance(signals, list)


if __name__ == "__main__":
    unittest.main()
