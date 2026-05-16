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
        data["ema_200"] = ema(data["close"], 200)  # Macro Trend Bias
        data["ema_fast"] = ema(data["close"], 21)  # Short-term momentum
        data["atr"] = atr(data, 14)                # Volatility Measurement
        data["rsi"] = rsi(data["close"], 14)       # Momentum Oscillator
        data["adx"] = adx(data, 14)                # Trend Strength
        
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
        if self._last_day != current_time.date():
            today_bars = data[data["time"].dt.date == current_time.date()]
            asian_session = today_bars[(today_bars["time"].dt.hour >= 0) & (today_bars["time"].dt.hour < 8)]
            
            if not asian_session.empty:
                self.asian_high = asian_session["high"].max()
                self.asian_low = asian_session["low"].min()
                self._last_day = current_time.date()

        # --- v18 TRADING WINDOW (London & NY Overlap 12:00 - 18:00 UTC) ---
        is_kill_zone = 12 <= current_hour <= 18
        if not is_kill_zone: return []

        # --- Read indicator values ---
        ema_200_val = float(last["ema_200"]) if not pd.isna(last.get("ema_200")) else None
        rsi_val = float(last["rsi"]) if not pd.isna(last.get("rsi")) else 50.0
        adx_val = float(last["adx"]) if not pd.isna(last.get("adx")) else 25.0
        rsi_buy_level = float(self.config.get("rsi_buy_level", 30))
        rsi_sell_level = float(self.config.get("rsi_sell_level", 70))
        min_adx = float(self.config.get("min_adx", 20))

        # --- FILTER 1: ADX Trend Strength (only trade when trend exists) ---
        if adx_val < min_adx:
            return []

        # --- INSTITUTIONAL BREAKOUT LOGIC ---
        # Requirement 1: Clean Break of Tokyo Range
        # Requirement 2: Price above/below EMA 21 (short-term momentum)
        # Requirement 3: EMA 200 Macro Trend Filter (don't counter-trade the trend)
        # Requirement 4: RSI not overbought/oversold
        
        buy_signal = (price > self.asian_high) and (price > last["ema_fast"])
        sell_signal = (price < self.asian_low) and (price < last["ema_fast"])

        # STR-1: EMA 200 Trend Filter — don't BUY in downtrend, don't SELL in uptrend
        if ema_200_val is not None:
            buy_signal = buy_signal and (price > ema_200_val)
            sell_signal = sell_signal and (price < ema_200_val)

        # STR-2: RSI Filter — avoid entries at extreme momentum
        buy_signal = buy_signal and (rsi_val < rsi_sell_level)   # Don't buy when overbought
        sell_signal = sell_signal and (rsi_val > rsi_buy_level)   # Don't sell when oversold

        # SL/TP Setup
        sl_dist = atr_val * float(self.config.get("atr_sl_multiplier", 2.5))
        rr = float(self.config.get("take_profit_rr", 3.0))

        # STR-4: Dynamic Confidence based on signal quality
        confidence = self._calculate_confidence(
            price=price,
            ema_200=ema_200_val,
            rsi=rsi_val,
            adx=adx_val,
            atr=atr_val,
        )

        signals: list[Signal] = []
        if buy_signal:
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=price,
                    sl=price - sl_dist,
                    tp=price + (sl_dist * rr),
                    confidence=confidence,
                    metadata={"type": "institutional", "atr": atr_val, "rsi": rsi_val, "adx": adx_val},
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
                    confidence=confidence,
                    metadata={"type": "institutional", "atr": atr_val, "rsi": rsi_val, "adx": adx_val},
                )
            )
        return signals

    def _calculate_confidence(
        self,
        price: float,
        ema_200: float | None,
        rsi: float,
        adx: float,
        atr: float,
    ) -> float:
        """
        STR-4: Dynamic confidence score (0.5 - 2.0) based on multiple factors.
        Higher confidence = more favorable conditions.
        """
        score = 1.0

        # Factor 1: Trend alignment strength (distance from EMA 200)
        if ema_200 and ema_200 > 0:
            trend_strength = abs(price - ema_200) / ema_200
            if trend_strength > 0.02:  # Strong trend (>2% from EMA)
                score += 0.2
            elif trend_strength > 0.01:  # Moderate trend
                score += 0.1

        # Factor 2: ADX strength
        if adx > 30:
            score += 0.2  # Strong trend
        elif adx > 25:
            score += 0.1  # Moderate trend

        # Factor 3: RSI not in extreme zones (best when RSI is mid-range)
        if 40 <= rsi <= 60:
            score += 0.1  # RSI in healthy range

        return round(min(2.0, max(0.5, score)), 2)
