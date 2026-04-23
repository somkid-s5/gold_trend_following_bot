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
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.last_win_time: datetime | None = None

    def update_equity_state(self, balance: float, equity: float) -> None:
        now = datetime.now(timezone.utc)
        if self.start_of_day_balance is None:
            self.start_of_day_balance = balance
            self._day_anchor = now.date()
        elif now.date() != self._day_anchor:
            self.start_of_day_balance = balance
            self._day_anchor = now.date()
        self.peak_equity = equity if self.peak_equity is None else max(self.peak_equity, equity)

    def is_paused_by_circuit_breaker(self, equity: float) -> RiskDecision:
        dd = self.total_drawdown_pct(equity)
        threshold = float(self.config.get("max_total_drawdown_pct", 95.0))
        if dd >= threshold:
            return RiskDecision(False, f"Circuit Breaker: Total Drawdown {dd:.1f}%")
        return RiskDecision(True)

    def update_trade_outcome(self, pnl: float) -> None:
        if pnl < 0:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        else:
            self.consecutive_losses = 0
            self.consecutive_wins += 1
            self.last_win_time = datetime.now(timezone.utc)

    def calculate_lot(
        self,
        equity: float,
        risk_pct: float,
        sl_distance_price: float,
        tick_size: float | None = None,
        tick_value: float | None = None,
        confidence_multiplier: float = 1.0,
    ) -> float:
        if sl_distance_price <= 0: return 0.01

        # --- HYPER BOOSTER 10.0X (THE FINAL BLOW) ---
        streak_multiplier = 1.0
        if self.consecutive_losses >= 2: streak_multiplier = 0.5
            
        win_boost = 1.0
        if self.consecutive_wins >= 4: win_boost = 10.0 # ALL-IN FOR THE MOON
        elif self.consecutive_wins >= 3: win_boost = 6.0
        elif self.consecutive_wins >= 2: win_boost = 3.5
        elif self.consecutive_wins >= 1: win_boost = 2.0

        effective_risk_pct = float(risk_pct) * win_boost * streak_multiplier
        risk_amount = float(equity) * (effective_risk_pct / 100.0)
        
        ts = float(tick_size or self.symbol_config.get("point", 0.01))
        tv = float(tick_value or (self.symbol_config.get("contract_size", 100) * ts))
        
        raw_lot = risk_amount / ((sl_distance_price / ts) * tv)
        step = float(self.symbol_config.get("lot_step", 0.01))
        final_lot = (raw_lot // step) * step
        return round(max(0.01, min(50.0, final_lot)), 2)

    def total_drawdown_pct(self, equity: float) -> float:
        if not self.peak_equity: return 0.0
        return max(0.0, ((self.peak_equity - equity) / self.peak_equity) * 100)

    def check_daily_dd(self, equity: float, max_daily_loss_pct: float | None = None) -> RiskDecision:
        threshold = max_daily_loss_pct or float(self.config["max_daily_loss_pct"])
        dd = max(0.0, ((self.start_of_day_balance - equity) / self.start_of_day_balance) * 100) if self.start_of_day_balance else 0.0
        if dd >= threshold: return RiskDecision(False, f"Daily DD: {dd:.1f}%")
        return RiskDecision(True)

    def check_spread(self, spread_points: float) -> RiskDecision:
        ms = float(self.config["max_spread_points"])
        if spread_points > ms: return RiskDecision(False, f"Spread: {spread_points:.1f}")
        return RiskDecision(True)

    def news_filter(self, now_utc: datetime, news_cfg: dict[str, Any]) -> RiskDecision:
        return RiskDecision(True)

    def breakeven_price(self, entry_price: float, sl_price: float, action: str) -> float:
        risk_dist = abs(entry_price - sl_price)
        trigger = float(self.config.get("breakeven_rr_trigger", 1.0))
        if action.upper() == "BUY": return entry_price + (risk_dist * trigger)
        return entry_price - (risk_dist * trigger)

    def trailing_stop_price(self, current_price: float, atr_value: float, action: str) -> float:
        multiple = float(self.config.get("trailing_stop_atr_multiple", 1.0))
        distance = atr_value * multiple
        if action.upper() == "BUY": return current_price - distance
        return current_price + distance
