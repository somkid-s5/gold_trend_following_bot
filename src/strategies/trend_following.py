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
        
        # Pre-calculate slope
        data["ema_slow_lookback"] = data["ema_slow"].shift(5)
        data["ema_slow_slope"] = (data["ema_slow"] - data["ema_slow_lookback"]) / data["ema_slow_lookback"] * 1000
        
        # Pre-calculate gap widening
        data["ema_gap"] = (data["ema_fast"] - data["ema_slow"]).abs()
        data["prev_ema_gap"] = data["ema_gap"].shift(1)
        data["gap_is_widening"] = data["ema_gap"] > data["prev_ema_gap"]
        
        return data

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        # If data is not prepared, prepare it (for live mode compatibility)
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
        
        if pd.isna(atr_value) or atr_value <= 0:
            return []

        rr = float(self.config["take_profit_rr"])
        sl_distance = atr_value * float(self.config["atr_sl_multiplier"])
        buy_level = float(self.config.get("rsi_buy_level", 40))
        sell_level = float(self.config.get("rsi_sell_level", 60))

        # ADX Multiplier: Aggressive scaling
        adx_multiplier = 1.0
        if adx_value > 25:
            adx_multiplier = min(1.8, adx_value / 20.0) 
        elif adx_value < 18:
            adx_multiplier = 0.5 

        # Use Pre-calculated Values
        ema_slow_slope = float(last["ema_slow_slope"])
        gap_is_widening = bool(last["gap_is_widening"])

        # Sideway Shield logic: Catching every trend
        is_sideway = adx_value < 18 or abs(ema_slow_slope) < 0.05
        sideway_penalty = 0.6 if is_sideway else 1.0 
        widening_bonus = 1.3 if gap_is_widening else 0.8

        if last["ema_fast"] > last["ema_slow"] and prev["rsi"] < buy_level <= last["rsi"]:
            entry = price
            rsi_factor = (last["rsi"] - prev["rsi"]) / 4.0 + 1.2
            confidence = round(rsi_factor * adx_multiplier * sideway_penalty * widening_bonus * 1.8, 2)
            confidence = max(0.5, min(5.0, confidence))
            
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=entry,
                    sl=entry - sl_distance,
                    tp=entry + (sl_distance * rr),
                    confidence=confidence,
                    metadata={"atr": atr_value, "adx": adx_value, "rsi": last["rsi"]},
                )
            )

        if last["ema_fast"] < last["ema_slow"] and prev["rsi"] > sell_level >= last["rsi"]:
            entry = price
            rsi_factor = (prev["rsi"] - last["rsi"]) / 4.0 + 1.2
            confidence = round(rsi_factor * adx_multiplier * sideway_penalty * widening_bonus * 1.8, 2)
            confidence = max(0.5, min(5.0, confidence))
            
            signals.append(
                Signal(
                    strategy=self.name,
                    action="SELL",
                    entry=entry,
                    sl=entry + sl_distance,
                    tp=entry - (sl_distance * rr),
                    confidence=confidence,
                    metadata={"atr": atr_value, "adx": adx_value, "rsi": last["rsi"]},
                )
            )
        return signals
