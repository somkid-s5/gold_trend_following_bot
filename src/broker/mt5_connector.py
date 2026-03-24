from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None


TIMEFRAME_MAP: dict[str, int] = {
    "M1": getattr(mt5, "TIMEFRAME_M1", 1),
    "M5": getattr(mt5, "TIMEFRAME_M5", 5),
    "M15": getattr(mt5, "TIMEFRAME_M15", 15),
    "M30": getattr(mt5, "TIMEFRAME_M30", 30),
    "H1": getattr(mt5, "TIMEFRAME_H1", 16385),
    "H4": getattr(mt5, "TIMEFRAME_H4", 16388),
    "D1": getattr(mt5, "TIMEFRAME_D1", 16408),
}


@dataclass(slots=True)
class AccountSnapshot:
    balance: float
    equity: float
    margin_free: float
    profit: float


class MT5Connector:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = False

    def connect_mt5(self) -> bool:
        if mt5 is None:
            raise ImportError("MetaTrader5 package is not installed. Run: pip install MetaTrader5")

        kwargs = {
            "login": self.config.get("login"),
            "password": self.config.get("password"),
            "server": self.config.get("server"),
            "timeout": self.config.get("timeout", 60_000),
        }
        if self.config.get("path"):
            kwargs["path"] = self.config["path"]

        self.initialized = bool(mt5.initialize(**kwargs))
        if not self.initialized:
            code, message = mt5.last_error()
            raise ConnectionError(f"MT5 initialize failed: {code} {message}")
        return True

    def disconnect(self) -> None:
        if mt5 is not None and self.initialized:
            mt5.shutdown()
        self.initialized = False

    def ensure_symbol(self, symbol: str) -> None:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"Symbol {symbol} not found in MT5")
        if not symbol_info.visible and not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Unable to select symbol {symbol}")

    def get_rates(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        self.ensure_symbol(symbol)
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME_MAP[timeframe], 0, count)
        if rates is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"copy_rates_from_pos failed: {code} {message}")

        frame = pd.DataFrame(rates)
        if frame.empty:
            raise ValueError(f"No MT5 bars returned for {symbol} on {timeframe}")

        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame.rename(columns={"tick_volume": "volume"}, inplace=True)
        return frame[["time", "open", "high", "low", "close", "volume", "spread", "real_volume"]]

    def get_symbol_tick(self, symbol: str) -> Any:
        self.ensure_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"symbol_info_tick failed: {code} {message}")
        return tick

    def get_symbol_info(self, symbol: str) -> Any:
        self.ensure_symbol(symbol)
        info = mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Unable to fetch symbol info for {symbol}")
        return info

    def get_positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"positions_get failed: {code} {message}")
        return [position._asdict() for position in positions]

    def send_order(
        self,
        symbol: str,
        action: str,
        volume: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> dict[str, Any]:
        tick = self.get_symbol_tick(symbol)
        order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if action.upper() == "BUY" else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.config.get("deviation", 20),
            "magic": self.config.get("magic_number", 0),
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"order_send failed: {code} {message}")
        payload = result._asdict()
        if payload["retcode"] != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order rejected: {payload}")
        return payload

    def modify_position(self, ticket: int, sl: float | None = None, tp: float | None = None) -> dict[str, Any]:
        position = mt5.positions_get(ticket=ticket)
        if not position:
            raise ValueError(f"Position {ticket} not found")
        current = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": current.symbol,
            "sl": sl if sl is not None else current.sl,
            "tp": tp if tp is not None else current.tp,
        }
        result = mt5.order_send(request)
        if result is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"modify_position failed: {code} {message}")
        return result._asdict()

    def close_position(self, ticket: int) -> dict[str, Any]:
        position = mt5.positions_get(ticket=ticket)
        if not position:
            raise ValueError(f"Position {ticket} not found")
        current = position[0]
        tick = self.get_symbol_tick(current.symbol)
        is_buy = current.type == mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": current.symbol,
            "volume": current.volume,
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "price": tick.bid if is_buy else tick.ask,
            "deviation": self.config.get("deviation", 20),
            "magic": self.config.get("magic_number", 0),
            "comment": "bot_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"close_position failed: {code} {message}")
        return result._asdict()

    def get_account_info(self) -> AccountSnapshot:
        info = mt5.account_info()
        if info is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"account_info failed: {code} {message}")
        data = info._asdict()
        return AccountSnapshot(
            balance=float(data["balance"]),
            equity=float(data["equity"]),
            margin_free=float(data["margin_free"]),
            profit=float(data["profit"]),
        )
