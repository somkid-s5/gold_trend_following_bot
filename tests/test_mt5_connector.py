from __future__ import annotations

import unittest
from unittest.mock import patch

from src.broker.mt5_connector import MT5Connector


class FakeResult:
    def __init__(self, retcode: int) -> None:
        self.retcode = retcode

    def _asdict(self) -> dict[str, int]:
        return {"retcode": self.retcode}


class FakeInfo:
    point = 0.01
    contract_size = 100
    filling_mode = 1


class FakeTick:
    ask = 3000.0
    bid = 2999.8


class MT5ConnectorTests(unittest.TestCase):
    def test_send_order_retries_timeout_then_succeeds(self) -> None:
        connector = MT5Connector(
            {
                "deviation": 20,
                "magic_number": 123,
                "order_retries": 2,
                "retry_delay_ms": 0,
            }
        )
        connector.get_symbol_info = lambda symbol: FakeInfo()
        connector.get_symbol_tick = lambda symbol: FakeTick()

        fake_mt5 = type(
            "FakeMT5",
            (),
            {
                "ORDER_TYPE_BUY": 0,
                "ORDER_TYPE_SELL": 1,
                "TRADE_ACTION_DEAL": 1,
                "ORDER_TIME_GTC": 0,
                "ORDER_FILLING_IOC": 1,
                "ORDER_FILLING_RETURN": 2,
                "ORDER_FILLING_FOK": 0,
                "TRADE_RETCODE_DONE": 10009,
                "TRADE_RETCODE_TIMEOUT": 10012,
                "TRADE_RETCODE_INVALID_FILL": 10030,
                "TRADE_RETCODE_REQUOTE": 10004,
                "TRADE_RETCODE_PRICE_CHANGED": 10020,
                "TRADE_RETCODE_PRICE_OFF": 10021,
                "TRADE_RETCODE_CONNECTION": 10031,
            },
        )()
        responses = [FakeResult(10012), FakeResult(10009)]
        fake_mt5.order_send = lambda request: responses.pop(0)
        fake_mt5.last_error = lambda: (0, "ok")

        with patch("src.broker.mt5_connector.mt5", fake_mt5):
            result = connector.send_order("XAUUSD", "BUY", 0.01, 2990.0, 3020.0, "test")

        self.assertEqual(result["retcode"], 10009)


if __name__ == "__main__":
    unittest.main()
