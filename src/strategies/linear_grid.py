from __future__ import annotations

from typing import Any

import pandas as pd

from src.strategies import Signal, atr, ema


class LinearGrid:
    name = "linear_grid"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.timeframe = config["timeframe"]

    def _zones(self, frame: pd.DataFrame) -> tuple[float, float]:
        lookback = int(self.config["zone_lookback"])
        window = frame.tail(lookback)
        supply = float(window["high"].max())
        demand = float(window["low"].min())
        return supply, demand

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        if len(frame) < max(
            self.config["zone_lookback"],
            self.config["atr_period"],
            self.config.get("trend_slow_ema", 1),
        ) + 5:
            return []

        context = context or {}
        data = frame.copy()
        data["atr"] = atr(data, self.config["atr_period"])
        data["ema_fast"] = ema(data["close"], int(self.config.get("trend_fast_ema", 34)))
        data["ema_slow"] = ema(data["close"], int(self.config.get("trend_slow_ema", 89)))
        last = data.iloc[-1]
        supply, demand = self._zones(data.iloc[:-1])
        atr_value = float(last["atr"])
        if atr_value <= 0:
            return []

        spacing = atr_value * float(self.config["spacing_atr_multiplier"])
        price = float(last["close"])
        existing_positions = int(context.get("existing_positions", 0))
        max_positions = int(self.config["max_positions"])
        current_drawdown = float(context.get("daily_drawdown_pct", 0.0))
        max_dd = float(context.get("max_daily_loss_pct", 3.0))
        if existing_positions >= max_positions or current_drawdown >= max_dd:
            return []

        midpoint = (supply + demand) / 2
        require_trend_alignment = bool(self.config.get("require_trend_alignment", True))
        allow_long = bool(self.config.get("allow_long", True))
        allow_short = bool(self.config.get("allow_short", True))
        trend_up = float(last["ema_fast"]) >= float(last["ema_slow"])
        trend_down = float(last["ema_fast"]) <= float(last["ema_slow"])
        zone_buffer = atr_value * float(self.config.get("zone_buffer_atr", 0.2))
        signals: list[Signal] = []

        if (
            allow_long
            and price <= demand + spacing + zone_buffer
            and (trend_up or not require_trend_alignment)
        ):
            entry = price
            global_tp = midpoint + (atr_value * float(self.config["take_profit_atr_multiplier"]))
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=entry,
                    sl=demand - (spacing * 1.2),
                    tp=global_tp,
                    confidence=0.68,
                    metadata={"supply": supply, "demand": demand, "grid_spacing": spacing, "trend": "up" if trend_up else "flat"},
                )
            )

        if (
            allow_short
            and price >= supply - spacing - zone_buffer
            and (trend_down or not require_trend_alignment)
        ):
            entry = price
            global_tp = midpoint - (atr_value * float(self.config["take_profit_atr_multiplier"]))
            signals.append(
                Signal(
                    strategy=self.name,
                    action="SELL",
                    entry=entry,
                    sl=supply + (spacing * 1.2),
                    tp=global_tp,
                    confidence=0.64,
                    metadata={"supply": supply, "demand": demand, "grid_spacing": spacing, "trend": "down" if trend_down else "flat"},
                )
            )

        return signals
