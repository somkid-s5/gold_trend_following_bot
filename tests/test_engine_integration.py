from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

import pandas as pd

from src.core.trading_engine import TradingEngine
from src.data.data_handler import DataHandler
from src.risk.risk_manager import RiskManager
from src.strategies import Signal
from src.utils.logger import setup_logger


class DummyStrategy:
    name = "trend_following"
    timeframe = "H1"

    def __init__(self, signal: Signal | None = None) -> None:
        self._signal = signal

    def generate_signals(self, frame: pd.DataFrame, context: dict | None = None) -> list[Signal]:
        return [self._signal] if self._signal is not None else []


class EngineIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "risk": {
                "risk_per_trade_pct": 1.0,
                "max_daily_loss_pct": 3.0,
                "max_total_drawdown_pct": 12.0,
                "max_spread_points": 30,
                "allow_strategy_addons": {"trend_following": 1},
                "breakeven_rr_trigger": 1.0,
                "trailing_stop_atr_multiple": 1.0,
                "close_all_on_daily_limit": True,
            },
            "news_filter": {"enabled": False, "provider": "manual", "high_impact_events": []},
            "trading": {"history_bars": {"trend_following": 50}},
            "operational_guards": {
                "enabled": True,
                "guard_report_path": "reports/test_guard_status.json",
                "pause_new_entries_on_trigger": True,
                "close_positions_on_trigger": False,
            },
        }
        self.symbol_cfg = {
            "point": 0.01,
            "contract_size": 100,
            "min_lot": 0.01,
            "max_lot": 20.0,
            "lot_step": 0.01,
        }
        self.risk_manager = RiskManager(self.config["risk"], self.symbol_cfg)
        self.data_handler = DataHandler()
        self.frame = pd.DataFrame(
            {
                "time": pd.date_range("2026-01-01", periods=50, freq="1h", tz="UTC"),
                "open": [2600 + i for i in range(50)],
                "high": [2601 + i for i in range(50)],
                "low": [2599 + i for i in range(50)],
                "close": [2600.5 + i for i in range(50)],
                "volume": [1500 for _ in range(50)],
            }
        )
        guard_path = self.config["operational_guards"]["guard_report_path"]
        if os.path.exists(guard_path):
            os.remove(guard_path)

    def _build_connector(self) -> MagicMock:
        connector = MagicMock()
        connector.get_account_info.return_value = type("Account", (), {"balance": 10_000.0, "equity": 10_000.0})()
        connector.get_symbol_info.return_value = type(
            "SymbolInfo",
            (),
            {"point": 0.01, "trade_tick_size": 0.01, "trade_tick_value": 1.0, "contract_size": 100},
        )()
        connector.get_symbol_tick.return_value = type("Tick", (), {"ask": 2630.0, "bid": 2629.8})()
        connector.get_positions.return_value = []
        connector.send_order.return_value = {"retcode": 10009}
        return connector

    def test_engine_executes_signal(self) -> None:
        connector = self._build_connector()
        strategy = DummyStrategy(
            Signal(
                strategy="trend_following",
                action="BUY",
                entry=2629.9,
                sl=2624.9,
                tp=2639.9,
                confidence=0.8,
            )
        )
        self.data_handler.get_live_bars = MagicMock(return_value=self.frame)
        engine = TradingEngine(
            connector=connector,
            data_handler=self.data_handler,
            risk_manager=self.risk_manager,
            strategies={"trend_following": strategy},
            config=self.config,
            logger=setup_logger("test_engine_executes"),
            mode="live",
        )
        results = engine.run("XAUUSD", "trend_following")
        self.assertEqual(results[0].status, "executed")
        connector.send_order.assert_called_once()

    def test_engine_manages_open_position(self) -> None:
        connector = self._build_connector()
        connector.get_positions.return_value = [
            {
                "ticket": 123,
                "type": 0,
                "price_open": 2620.0,
                "sl": 2615.0,
                "tp": 2630.0,
                "comment": "trend_following|conf=0.80",
            }
        ]
        self.data_handler.get_live_bars = MagicMock(return_value=self.frame)
        engine = TradingEngine(
            connector=connector,
            data_handler=self.data_handler,
            risk_manager=self.risk_manager,
            strategies={"trend_following": DummyStrategy(None)},
            config=self.config,
            logger=setup_logger("test_engine_manage"),
            mode="live",
        )
        results = engine.run("XAUUSD", "trend_following")
        self.assertTrue(any(item.status == "managed" for item in results))
        connector.modify_position.assert_called()

    def test_engine_pauses_when_guard_file_requests_pause(self) -> None:
        guard_path = self.config["operational_guards"]["guard_report_path"]
        with open(guard_path, "w", encoding="utf-8") as handle:
            handle.write('{"status":"PAUSE","reasons":["Loss streak exceeded"],"metrics":{"total_trades":25}}')
        connector = self._build_connector()
        self.data_handler.get_live_bars = MagicMock(return_value=self.frame)
        engine = TradingEngine(
            connector=connector,
            data_handler=self.data_handler,
            risk_manager=self.risk_manager,
            strategies={"trend_following": DummyStrategy(None)},
            config=self.config,
            logger=setup_logger("test_engine_pause"),
            mode="live",
        )
        results = engine.run("XAUUSD", "trend_following")
        self.assertEqual(results[0].status, "paused")
        connector.send_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
