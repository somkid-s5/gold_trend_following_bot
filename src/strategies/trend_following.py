from __future__ import annotations

from typing import Any
import pandas as pd
import numpy as np
from src.strategies import Signal, atr, ema, rsi, adx


class TrendFollowing:
    name = "titan_v18_institutional"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.timeframe = config["timeframe"]
        self.asian_high = 0.0
        self.asian_low = 0.0
        self._last_day = None

    def prepare_data(self, frame: pd.DataFrame) -> pd.DataFrame:
        data = frame.copy()
        
        # Institutional Indicators
        data["ema_200"] = ema(data["close"], 200) # Trend Bias
        data["atr"] = atr(data, 14)               # Volatility Measurement
        data["rsi"] = rsi(data["close"], 14)      # Momentum
        data["ema_fast"] = ema(data["close"], 21)
        
        return data

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        if "ema_200" not in frame.columns:
            data = self.prepare_data(frame)
        else:
            data = frame

        if len(data) < 2: return []
            
        last = data.iloc[-1]
        prev = data.iloc[-2]
        
        current_time = last["time"]
        current_hour = current_time.hour
        price = float(last["close"])
        atr_val = float(last["atr"])
        
        if pd.isna(atr_val) or atr_val <= 0: return []

        # --- v18 INSTITUTIONAL: TOKYO RANGE DETECTOR (00:00 - 08:00 UTC) ---
        # If it's a new day, reset ranges
        if self._last_day != current_time.date():
            # Get all bars from today 00:00 to 08:00
            today_bars = data[data["time"].dt.date == current_time.date()]
            asian_session = today_bars[(today_bars["time"].dt.hour >= 0) & (today_bars["time"].dt.hour < 8)]
            
            if not asian_session.empty:
                self.asian_high = asian_session["high"].max()
                self.asian_low = asian_session["low"].min()
                self._last_day = current_time.date()

        # --- v18 TRADING WINDOW (London & NY Overlap 12:00 - 18:00 UTC) ---
        is_kill_zone = 12 <= current_hour <= 18
        if not is_kill_zone: return []

        # --- INSTITUTIONAL BREAKOUT LOGIC ---
        # Requirement 1: Macro Trend (Price > EMA 200 for BUY)
        # Requirement 2: Clean Break of Tokyo Range (Price > asian_high)
        # Requirement 3: Volatility Check (Price must be moving fast)
        
        buy_signal = (price > self.asian_high) and (price > last["ema_200"]) and (price > last["ema_fast"])
        sell_signal = (price < self.asian_low) and (price < last["ema_200"]) and (price < last["ema_fast"])

        # SL/TP Setup: Tight Institutional Risk
        sl_dist = atr_val * 1.5
        rr = 10.0 # AIM FOR THE TITAN 100K 

        signals: list[Signal] = []
        if buy_signal:
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=price,
                    sl=price - sl_dist,
                    tp=price + (sl_dist * rr),
                    confidence=1.5, # High confidence for breakouts
                    metadata={"type": "institutional", "atr": atr_val},
                )
            )

        if sell_signal:
            signals.append(
                Signal(
                    strategy=self.name,
                    action="SELL",
                    entry=price,
                    sl=price + sl_dist,
                    tp=price - (sl_dist * rr),
                    confidence=1.5,
                    metadata={"type": "institutional", "atr": atr_val},
                )
            )
        return signals
