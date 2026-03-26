from __future__ import annotations

from datetime import time
from typing import Any

import pandas as pd

from src.strategies import Signal, atr, ema, macd


class ScalpingSMC:
    name = "scalping_smc"

    def __init__(self, config: dict[str, Any], session_cfg: dict[str, Any]) -> None:
        self.config = config
        self.timeframe = config["timeframe"]
        start_h, start_m = map(int, session_cfg["start_utc"].split(":"))
        end_h, end_m = map(int, session_cfg["end_utc"].split(":"))
        self.session_start = time(start_h, start_m)
        self.session_end = time(end_h, end_m)

    def _within_session(self, timestamp: pd.Timestamp) -> bool:
        current = timestamp.tz_convert("UTC").time()
        return self.session_start <= current <= self.session_end

    def _find_fvg_bias(self, frame: pd.DataFrame) -> str | None:
        last3 = frame.tail(3).reset_index(drop=True)
        if len(last3) < 3:
            return None
        if last3.loc[2, "low"] > last3.loc[0, "high"]:
            return "BUY"
        if last3.loc[2, "high"] < last3.loc[0, "low"]:
            return "SELL"
        return None

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        if len(frame) < max(self.config["volume_window"], self.config["macd_slow"], self.config["trend_slow_ema"]) + 5:
            return []
        data = frame.copy()
        data["bb_mid"] = data["close"].rolling(self.config["bb_period"]).mean()
        data["bb_std"] = data["close"].rolling(self.config["bb_period"]).std()
        data["bb_upper"] = data["bb_mid"] + (data["bb_std"] * float(self.config["bb_std"]))
        data["bb_lower"] = data["bb_mid"] - (data["bb_std"] * float(self.config["bb_std"]))
        data["bb_width"] = (data["bb_upper"] - data["bb_lower"]) / data["bb_mid"]
        data["ema_fast"] = ema(data["close"], self.config["trend_fast_ema"])
        data["ema_slow"] = ema(data["close"], self.config["trend_slow_ema"])
        data["atr"] = atr(data, self.config["atr_period"])
        _, _, hist = macd(
            data["close"],
            self.config["macd_fast"],
            self.config["macd_slow"],
            self.config["macd_signal"],
        )
        data["macd_hist"] = hist
        data["volume_mean"] = data["volume"].rolling(self.config["volume_window"]).mean()

        last = data.iloc[-1]
        prev = data.iloc[-2]
        if not self._within_session(last["time"]):
            return []

        squeeze_threshold = data["bb_width"].rolling(50).quantile(float(self.config.get("squeeze_quantile", 0.2))).iloc[-1]
        if pd.isna(squeeze_threshold):
            return []

        volume_ratio = float(last["volume"]) / float(last["volume_mean"]) if float(last["volume_mean"]) > 0 else 0.0
        volume_burst = volume_ratio >= float(self.config.get("min_volume_ratio", 1.15))
        bullish_fvg = self._find_fvg_bias(data.iloc[:-1]) == "BUY"
        bearish_fvg = self._find_fvg_bias(data.iloc[:-1]) == "SELL"
        require_fvg = bool(self.config.get("require_fvg", True))
        allow_long = bool(self.config.get("allow_long", True))
        allow_short = bool(self.config.get("allow_short", True))
        atr_value = float(last["atr"])
        if atr_value <= 0:
            return []
        sl_distance = atr_value * float(self.config["atr_sl_multiplier"])
        rr = float(self.config["take_profit_rr"])
        trend_up = float(last["ema_fast"]) > float(last["ema_slow"]) and float(last["close"]) > float(last["ema_slow"])
        trend_down = float(last["ema_fast"]) < float(last["ema_slow"]) and float(last["close"]) < float(last["ema_slow"])
        breakout_distance_up = float(last["close"] - last["bb_upper"])
        breakout_distance_down = float(last["bb_lower"] - last["close"])
        min_breakout = atr_value * float(self.config.get("breakout_atr_fraction", 0.15))
        macd_accel_up = float(last["macd_hist"]) > float(prev["macd_hist"])
        macd_accel_down = float(last["macd_hist"]) < float(prev["macd_hist"])

        signals: list[Signal] = []
        breakout_up = prev["close"] <= prev["bb_upper"] and last["close"] > last["bb_upper"]
        breakout_down = prev["close"] >= prev["bb_lower"] and last["close"] < last["bb_lower"]

        if (
            allow_long
            and
            float(last["bb_width"]) <= float(squeeze_threshold)
            and breakout_up
            and trend_up
            and volume_burst
            and float(last["macd_hist"]) > 0
            and macd_accel_up
            and breakout_distance_up >= min_breakout
            and (bullish_fvg or not require_fvg)
        ):
            entry = float(last["close"])
            signals.append(
                Signal(
                    strategy=self.name,
                    action="BUY",
                    entry=entry,
                    sl=entry - sl_distance,
                    tp=entry + (sl_distance * rr),
                    confidence=0.72,
                    metadata={"atr": atr_value, "volume_ratio": volume_ratio},
                )
            )

        if (
            allow_short
            and
            float(last["bb_width"]) <= float(squeeze_threshold)
            and breakout_down
            and trend_down
            and volume_burst
            and float(last["macd_hist"]) < 0
            and macd_accel_down
            and breakout_distance_down >= min_breakout
            and (bearish_fvg or not require_fvg)
        ):
            entry = float(last["close"])
            signals.append(
                Signal(
                    strategy=self.name,
                    action="SELL",
                    entry=entry,
                    sl=entry + sl_distance,
                    tp=entry - (sl_distance * rr),
                    confidence=0.7,
                    metadata={"atr": atr_value, "volume_ratio": volume_ratio},
                )
            )

        return signals
