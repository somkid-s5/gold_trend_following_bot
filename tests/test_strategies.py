from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from src.strategies.trend_following import TrendFollowing


def build_frame(closes: list[float], volume_base: int = 1500) -> list[dict[str, object]]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []
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
    return rows


class TrendFollowingStrategyTests(unittest.TestCase):
    def test_trend_following_generates_buy_signal(self) -> None:
        import pandas as pd

        closes = [1800 + i * 0.6 for i in range(205)] + [1918, 1912, 1908, 1904, 1912]
        frame = pd.DataFrame(build_frame(closes))
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


if __name__ == "__main__":
    unittest.main()
