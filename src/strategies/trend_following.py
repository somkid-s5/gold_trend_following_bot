from __future__ import annotations

from typing import Any

import pandas as pd

from src.strategies import Signal, atr, ema, rsi


class TrendFollowing:
    name = "trend_following"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.timeframe = config["timeframe"]

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        if len(frame) < max(self.config["slow_ema"], self.config["atr_period"]) + 5:
            return []

        data = frame.copy()
        data["ema_fast"] = ema(data["close"], self.config["fast_ema"])
        data["ema_slow"] = ema(data["close"], self.config["slow_ema"])
        data["rsi"] = rsi(data["close"], self.config["rsi_period"])
        data["atr"] = atr(data, self.config["atr_period"])
        last = data.iloc[-1]
        prev = data.iloc[-2]

        signals: list[Signal] = []
        atr_value = float(last["atr"])
        if pd.isna(atr_value) or atr_value <= 0:
            return []

        rr = float(self.config["take_profit_rr"])
        sl_distance = atr_value * float(self.config["atr_sl_multiplier"])
        buy_level = float(self.config.get("rsi_buy_level", 40))
        sell_level = float(self.config.get("rsi_sell_level", 60))

        if last["ema_fast"] > last["ema_slow"] and prev["rsi"] < buy_level <= last["rsi"]:
            entry = float(last["close"])
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=entry,
                    sl=entry - sl_distance,
                    tp=entry + (sl_distance * rr),
                    confidence=0.8,
                    metadata={"atr": atr_value},
                )
            )

        if last["ema_fast"] < last["ema_slow"] and prev["rsi"] > sell_level >= last["rsi"]:
            entry = float(last["close"])
            signals.append(
                Signal(
                    strategy=self.name,
                    action="SELL",
                    entry=entry,
                    sl=entry + sl_distance,
                    tp=entry - (sl_distance * rr),
                    confidence=0.8,
                    metadata={"atr": atr_value},
                )
            )

        return signals
