from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd


@dataclass(slots=True)
class Signal:
    strategy: str
    action: str
    entry: float
    sl: float
    tp: float
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class Strategy(Protocol):
    name: str
    timeframe: str

    def generate_signals(self, frame: pd.DataFrame, context: dict[str, Any] | None = None) -> list[Signal]:
        ...


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return 100 - (100 / (1 + rs))


def atr(frame: pd.DataFrame, period: int) -> pd.Series:
    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def macd(series: pd.Series, fast: int, slow: int, signal: int) -> tuple[pd.Series, pd.Series, pd.Series]:       
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    line = fast_ema - slow_ema
    signal_line = ema(line, signal)
    hist = line - signal_line
    return line, signal_line, hist


def adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    plus_dm = frame["high"].diff()
    minus_dm = frame["low"].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = minus_dm.abs()

    # Use standard DM/TR filtering
    plus_dm.loc[plus_dm < minus_dm] = 0
    minus_dm.loc[minus_dm < plus_dm] = 0

    tr = atr(frame, 1) # True Range
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr(frame, period))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr(frame, period))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1/period, adjust=False).mean()
