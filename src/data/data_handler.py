from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.broker.mt5_connector import MT5Connector


class DataHandler:
    def __init__(self, connector: MT5Connector | None = None) -> None:
        self.connector = connector

    def get_live_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        if self.connector is None:
            raise ValueError("MT5Connector is required for live data access")
        frame = self.connector.get_rates(symbol, timeframe, count)
        return frame.sort_values("time").reset_index(drop=True)

    def load_csv(self, csv_path: str | Path) -> pd.DataFrame:
        frame = pd.read_csv(csv_path)
        if "time" not in frame.columns:
            raise ValueError("CSV must contain a 'time' column")
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        required = {"open", "high", "low", "close", "volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")
        return frame.sort_values("time").reset_index(drop=True)

    def resample(self, frame: pd.DataFrame, rule: str) -> pd.DataFrame:
        indexed = frame.set_index("time")
        resampled = indexed.resample(rule).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        resampled.dropna(inplace=True)
        return resampled.reset_index()
