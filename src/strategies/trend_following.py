from __future__ import annotations

from typing import Any

import pandas as pd

from src.strategies import Signal, atr, ema, rsi, adx


class TrendFollowing:
    name = "trend_following"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.timeframe = config["timeframe"]

    def prepare_data(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators at once for maximum speed."""
        data = frame.copy()
        data["ema_fast"] = ema(data["close"], self.config["fast_ema"])
        data["ema_slow"] = ema(data["close"], self.config["slow_ema"])
        data["rsi"] = rsi(data["close"], self.config["rsi_period"])
        data["atr"] = atr(data, self.config["atr_period"])
        data["adx"] = adx(data, 14)
        
        # v3 FAST D1 TREND FILTER (EMA 1200)
        data["ema_d1_trend"] = ema(data["close"], 1200) 
        
        # Pre-calculate slope
        data["ema_slow_lookback"] = data["ema_slow"].shift(5)
        data["ema_slow_slope"] = (data["ema_slow"] - data["ema_slow_lookback"]) / data["ema_slow_lookback"] * 1000
        
        # Pre-calculate gap widening
        data["ema_gap"] = (data["ema_fast"] - data["ema_slow"]).abs()
        data["prev_ema_gap"] = data["ema_gap"].shift(1)
        data["gap_is_widening"] = data["ema_gap"] > data["prev_ema_gap"]
        
        return data

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        if "ema_fast" not in frame.columns:
            data = self.prepare_data(frame)
        else:
            data = frame

        if len(data) < 2:
            return []
            
        last = data.iloc[-1]
        prev = data.iloc[-2]

        signals: list[Signal] = []
        atr_value = float(last["atr"])
        adx_value = float(last["adx"])
        price = float(last["close"])
        d1_trend = float(last["ema_d1_trend"])
        
        if pd.isna(atr_value) or atr_value <= 0:
            return []

        # --- v5 SNIPER UPGRADE: EXTENDED SESSION (UTC 10:00 - 22:00) ---
        current_hour = last["time"].hour
        is_sniper_hour = 10 <= current_hour <= 22
        if not is_sniper_hour: return []

        # --- v3 UPGRADE: DYNAMIC RR ---
        rr = 5.0 if adx_value > 25 else 3.5
        sl_distance = atr_value * 2.0
        
        # Trend Direction
        can_buy = price > d1_trend and last["ema_fast"] > last["ema_slow"]
        can_sell = price < d1_trend and last["ema_fast"] < last["ema_slow"]

        # --- FINAL BERSERKER: MULTI-ENTRY PULLBACK ---
        # 1. Standard Crossover Entry
        buy_cross = prev["rsi"] < 35 <= last["rsi"]
        sell_cross = prev["rsi"] > 65 >= last["rsi"]
        
        # 2. Pullback Entry (More aggressive during strong trends)
        buy_pullback = adx_value > 20 and prev["rsi"] < 45 <= last["rsi"]
        sell_pullback = adx_value > 20 and prev["rsi"] > 55 >= last["rsi"]

        if can_buy and (buy_cross or buy_pullback):
            confidence = round((adx_value / 10.0) * 1.5, 2)
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=price,
                    sl=price - sl_distance,
                    tp=price + (sl_distance * rr),
                    confidence=max(1.0, min(10.0, confidence)),
                    metadata={"atr": atr_value, "adx": adx_value, "type": "hyper"},
                )
            )

        if can_sell and (sell_cross or sell_pullback):
            confidence = round((adx_value / 10.0) * 1.5, 2)
            signals.append(
                Signal(
                    strategy=self.name,
                    action="SELL",
                    entry=price,
                    sl=price + sl_distance,
                    tp=price - (sl_distance * rr),
                    confidence=max(1.0, min(10.0, confidence)),
                    metadata={"atr": atr_value, "adx": adx_value, "type": "hyper"},
                )
            )
        return signals
