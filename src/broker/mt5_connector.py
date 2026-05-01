from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import time
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
            # Try upper case fallback
            symbol = symbol.upper()
            symbol_info = mt5.symbol_info(symbol)
            
        if symbol_info is None:
            raise ValueError(f"Symbol {symbol} not found in MT5 Market Watch")
        if not symbol_info.visible and not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Unable to select symbol {symbol} for trading")

    def get_rates(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        self.ensure_symbol(symbol)
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME_MAP[timeframe], 0, count)
        if rates is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"MT5: Failed to fetch {count} bars for {symbol}: [{code}] {message}")

        frame = pd.DataFrame(rates)
        if frame.empty:
            raise ValueError(f"MT5: No rates returned for {symbol}")

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
        symbol_info = self.get_symbol_info(symbol)
        order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        
        retries = max(int(self.config.get("order_retries", 3)), 0)
        retry_delay = max(float(self.config.get("retry_delay_ms", 1000)), 0.0) / 1000.0

        filling_modes = self._candidate_filling_modes(symbol_info)
        last_error_msg = "Order not sent"

        for filling_mode in filling_modes:
            for attempt in range(retries + 1):
                tick = self.get_symbol_tick(symbol)
                price = tick.ask if action.upper() == "BUY" else tick.bid
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(volume),
                    "type": order_type,
                    "price": float(price),
                    "sl": float(sl),
                    "tp": float(tp),
                    "deviation": int(self.config.get("deviation", 20)),
                    "magic": int(self.config.get("magic_number", 260324)),
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling_mode,
                }
                
                result = mt5.order_send(request)
                if result is None:
                    code, msg = mt5.last_error()
                    last_error_msg = f"Internal Error: [{code}] {msg}"
                    if attempt < retries:
                        time.sleep(retry_delay)
                        continue
                    break

                payload = result._asdict()
                retcode = int(payload.get("retcode", -1))
                if retcode == mt5.TRADE_RETCODE_DONE:
                    return payload

                last_error_msg = f"Broker Error [{retcode}]: {payload.get('comment', 'Rejected')}"
                if self._is_fill_mode_error(retcode):
                    break # Try next filling mode
                if self._is_retryable_retcode(retcode) and attempt < retries:
                    time.sleep(retry_delay)
                    continue
                break

        raise RuntimeError(f"MT5 Order Execution Failed for {symbol} {action}: {last_error_msg}")

    def _candidate_filling_modes(self, symbol_info: Any) -> list[int]:
        preferred = getattr(symbol_info, "filling_mode", None)
        fallbacks = [
            preferred,
            getattr(mt5, "ORDER_FILLING_IOC", None),
            getattr(mt5, "ORDER_FILLING_RETURN", None),
            getattr(mt5, "ORDER_FILLING_FOK", None),
        ]
        unique: list[int] = []
        for mode in fallbacks:
            if mode is None or mode in unique:
                continue
            unique.append(int(mode))
        return unique or [getattr(mt5, "ORDER_FILLING_IOC", 1)]

    def _is_retryable_retcode(self, retcode: int) -> bool:
        retryable = {
            getattr(mt5, "TRADE_RETCODE_TIMEOUT", 10012),
            getattr(mt5, "TRADE_RETCODE_REQUOTE", 10004),
            getattr(mt5, "TRADE_RETCODE_PRICE_CHANGED", 10020),
            getattr(mt5, "TRADE_RETCODE_PRICE_OFF", 10021),
            getattr(mt5, "TRADE_RETCODE_CONNECTION", 10031),
        }
        return retcode in retryable

    def _is_fill_mode_error(self, retcode: int) -> bool:
        fill_errors = {
            getattr(mt5, "TRADE_RETCODE_INVALID_FILL", 10030),
        }
        return retcode in fill_errors

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

    def get_total_invested_capital(self) -> float:
        """
        Automatically scans MT5 history to find all deposits and withdrawals.
        DEAL_TYPE_BALANCE (value 2) identifies these operations.
        """
        if not self.initialized and not self.connect_mt5():
            return 0.0
            
        # Scan from account inception
        date_from = datetime(2010, 1, 1)
        date_to = datetime.now()
        
        deals = mt5.history_deals_get(date_from, date_to)
        if deals is None:
            return 0.0
            
        total_invested = 0.0
        # DEAL_TYPE_BALANCE = 2
        for d in deals:
            if d.type == 2: # Deposit/Withdrawal/Adjustment
                total_invested += d.profit
                
        return total_invested

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

    def get_history_deals(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        deals = mt5.history_deals_get(date_from, date_to)
        if deals is None:
            code, message = mt5.last_error()
            raise RuntimeError(f"history_deals_get failed: {code} {message}")
        rows = [deal._asdict() for deal in deals]
        if symbol:
            rows = [row for row in rows if row.get("symbol") == symbol]
        return rows

    def get_strategy_closed_trades(
        self,
        symbol: str,
        strategy_name: str,
        lookback_days: int,
        current_balance: float | None = None,
    ) -> pd.DataFrame:
        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=lookback_days)
        deals = self.get_history_deals(date_from, date_to, symbol=symbol)
        if not deals:
            return pd.DataFrame(columns=["time", "strategy", "pnl", "balance"])

        entry_in = getattr(mt5, "DEAL_ENTRY_IN", 0)
        entry_out = getattr(mt5, "DEAL_ENTRY_OUT", 1)
        position_strategy: dict[int, str] = {}
        closed_rows: list[dict[str, Any]] = []

        for deal in deals:
            position_id = int(deal.get("position_id", 0))
            comment = str(deal.get("comment", "") or "")
            entry = int(deal.get("entry", -1))
            if entry == entry_in and strategy_name in comment:
                position_strategy[position_id] = strategy_name
            elif entry == entry_out:
                mapped_strategy = position_strategy.get(position_id)
                if not mapped_strategy and strategy_name in comment:
                    mapped_strategy = strategy_name
                if mapped_strategy != strategy_name:
                    continue
                pnl = float(deal.get("profit", 0.0)) + float(deal.get("swap", 0.0)) + float(deal.get("commission", 0.0)) + float(deal.get("fee", 0.0))
                closed_rows.append(
                    {
                        "time": pd.to_datetime(int(deal["time"]), unit="s", utc=True),
                        "strategy": strategy_name,
                        "pnl": pnl,
                    }
                )

        frame = pd.DataFrame(closed_rows)
        if frame.empty:
            return pd.DataFrame(columns=["time", "strategy", "pnl", "balance"])
        frame.sort_values("time", inplace=True)
        frame.reset_index(drop=True, inplace=True)
        if current_balance is None:
            current_balance = float(self.get_account_info().balance)
        starting_balance = current_balance - float(frame["pnl"].sum())
        frame["balance"] = starting_balance + frame["pnl"].cumsum()
        return frame
