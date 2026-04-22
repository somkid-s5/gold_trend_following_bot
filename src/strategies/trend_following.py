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
        data["d1_filter"] = ema(data["close"], 1200)
        
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
        d1_trend = float(last["d1_filter"])
        
        if pd.isna(atr_value) or atr_value <= 0:
            return []

        rr = float(self.config["take_profit_rr"])
        sl_distance = atr_value * float(self.config["atr_sl_multiplier"])
        buy_level = float(self.config.get("rsi_buy_level", 40))
        sell_level = float(self.config.get("rsi_sell_level", 60))

        # ADX Multiplier
        adx_multiplier = 1.0
        if adx_value > 25:
            adx_multiplier = min(1.5, adx_value / 25.0)
        elif adx_value < 20:
            adx_multiplier = 0.2 

        # Use Pre-calculated Values (already in 'last' row from prepare_data)
        ema_slow_slope = float(last["ema_slow_slope"])
        gap_is_widening = bool(last["gap_is_widening"])

        # Sideway Shield logic
        is_sideway = adx_value < 20 or abs(ema_slow_slope) < 0.1
        sideway_penalty = 0.2 if is_sideway else 1.0 # Stronger penalty
        widening_bonus = 1.2 if gap_is_widening else 0.7

        # --- D1 FILTER LOGIC ---
        # Only BUY if price is above D1 Filter, Only SELL if below
        # This prevents trading against the primary multi-month trend
        can_buy = price > d1_trend * 1.002 # 0.2% buffer
        can_sell = price < d1_trend * 0.998

        if last["ema_fast"] > last["ema_slow"] and prev["rsi"] < buy_level <= last["rsi"]:
            if can_buy:
                entry = price
                rsi_factor = (last["rsi"] - prev["rsi"]) / 5.0 + 1.0
                confidence = round(rsi_factor * adx_multiplier * sideway_penalty * widening_bonus * 1.5, 2)
                confidence = max(0.4, min(5.0, confidence))                
                signals.append(
                    Signal(
                        strategy=self.name,
                        action="BUY",
                        entry=entry,
                        sl=entry - sl_distance,
                        tp=entry + (sl_distance * rr),
                        confidence=confidence,
                        metadata={"atr": atr_value, "adx": adx_value, "d1_dist": price/d1_trend},
                    )
                )

        if last["ema_fast"] < last["ema_slow"] and prev["rsi"] > sell_level >= last["rsi"]:
            if can_sell:
                entry = price
                rsi_factor = (prev["rsi"] - last["rsi"]) / 5.0 + 1.0
                confidence = round(rsi_factor * adx_multiplier * sideway_penalty * 1.5, 2)
                confidence = max(0.4, min(5.0, confidence))
                
                signals.append(
                    Signal(
                        strategy=self.name,
                        action="SELL",
                        entry=entry,
                        sl=entry + sl_distance,
                        tp=entry - (sl_distance * rr),
                        confidence=confidence,
                        metadata={"atr": atr_value, "adx": adx_value, "d1_dist": price/d1_trend},
                    )
                )
        return signals
