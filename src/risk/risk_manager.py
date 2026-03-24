from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reason: str = ""


class RiskManager:
    def __init__(self, config: dict[str, Any], symbol_config: dict[str, Any]) -> None:
        self.config = config
        self.symbol_config = symbol_config
        self.start_of_day_balance: float | None = None
        self.peak_equity: float | None = None
        self._day_anchor = datetime.now(timezone.utc).date()

    def update_equity_state(self, balance: float, equity: float) -> None:
        now = datetime.now(timezone.utc)
        if self.start_of_day_balance is None:
            self.start_of_day_balance = balance
            self._day_anchor = now.date()
        elif now.date() != self._day_anchor:
            self.start_of_day_balance = balance
            self._day_anchor = now.date()

        self.peak_equity = equity if self.peak_equity is None else max(self.peak_equity, equity)

    def calculate_lot(
        self,
        equity: float,
        risk_pct: float,
        sl_distance_price: float,
        tick_size: float | None = None,
        tick_value: float | None = None,
    ) -> float:
        if sl_distance_price <= 0:
            raise ValueError("sl_distance_price must be positive")

        risk_amount = equity * (risk_pct / 100)
        tick_size = tick_size or self.symbol_config.get("point", 0.01)
        tick_value = tick_value or (self.symbol_config.get("contract_size", 100) * tick_size)
        stop_ticks = sl_distance_price / tick_size
        if stop_ticks <= 0 or tick_value <= 0:
            raise ValueError("Invalid symbol tick information for lot calculation")

        raw_lot = risk_amount / (stop_ticks * tick_value)
        min_lot = float(self.symbol_config.get("min_lot", 0.01))
        max_lot = float(self.symbol_config.get("max_lot", 100.0))
        step = float(self.symbol_config.get("lot_step", 0.01))
        stepped = max(min_lot, min(max_lot, round(raw_lot / step) * step))
        return round(stepped, 2)

    def daily_drawdown_pct(self, equity: float) -> float:
        if not self.start_of_day_balance:
            return 0.0
        return max(0.0, ((self.start_of_day_balance - equity) / self.start_of_day_balance) * 100)

    def total_drawdown_pct(self, equity: float) -> float:
        if not self.peak_equity:
            return 0.0
        return max(0.0, ((self.peak_equity - equity) / self.peak_equity) * 100)

    def check_daily_dd(self, equity: float, max_daily_loss_pct: float | None = None) -> RiskDecision:
        threshold = max_daily_loss_pct or float(self.config["max_daily_loss_pct"])
        dd = self.daily_drawdown_pct(equity)
        if dd >= threshold:
            return RiskDecision(False, f"Daily drawdown limit exceeded: {dd:.2f}% >= {threshold:.2f}%")
        return RiskDecision(True)

    def check_total_dd(self, equity: float, max_total_dd_pct: float | None = None) -> RiskDecision:
        threshold = max_total_dd_pct or float(self.config["max_total_drawdown_pct"])
        dd = self.total_drawdown_pct(equity)
        if dd >= threshold:
            return RiskDecision(False, f"Total drawdown limit exceeded: {dd:.2f}% >= {threshold:.2f}%")
        return RiskDecision(True)

    def check_spread(self, spread_points: float) -> RiskDecision:
        max_spread = float(self.config["max_spread_points"])
        if spread_points > max_spread:
            return RiskDecision(False, f"Spread too high: {spread_points:.1f} > {max_spread:.1f}")
        return RiskDecision(True)

    def news_filter(self, now_utc: datetime, news_cfg: dict[str, Any]) -> RiskDecision:
        if not news_cfg.get("enabled", False):
            return RiskDecision(True)
        minutes_before = int(news_cfg.get("minutes_before", 45))
        minutes_after = int(news_cfg.get("minutes_after", 30))
        events = news_cfg.get("resolved_events", news_cfg.get("high_impact_events", []))

        for event in events:
            event_time = datetime.fromisoformat(event)
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            start = event_time - timedelta(minutes=minutes_before)
            end = event_time + timedelta(minutes=minutes_after)
            if start <= now_utc <= end:
                return RiskDecision(False, f"News filter active around {event_time.isoformat()}")
        return RiskDecision(True)

    def breakeven_price(self, entry_price: float, sl_price: float, action: str) -> float:
        risk_distance = abs(entry_price - sl_price)
        trigger_multiple = float(self.config.get("breakeven_rr_trigger", 1.0))
        if action.upper() == "BUY":
            return entry_price + (risk_distance * trigger_multiple)
        return entry_price - (risk_distance * trigger_multiple)

    def trailing_stop_price(self, current_price: float, atr_value: float, action: str) -> float:
        multiple = float(self.config.get("trailing_stop_atr_multiple", 1.0))
        distance = atr_value * multiple
        if action.upper() == "BUY":
            return current_price - distance
        return current_price + distance
