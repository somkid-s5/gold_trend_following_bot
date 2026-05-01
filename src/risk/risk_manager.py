from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reason: str = ""


class RiskManager:
    def __init__(self, config: dict[str, Any], symbols_config: dict[str, Any]) -> None:
        self.config = config
        self.symbols_config = symbols_config
        self.start_of_day_balance: float | None = None
        self.peak_equity: float | None = None
        self._day_anchor = datetime.now(timezone.utc).date()
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.realized_trading_profit = 0.0 

    def update_equity_state(self, balance: float, equity: float) -> None:
        now = datetime.now(timezone.utc)
        if self.start_of_day_balance is None or now.date() != self._day_anchor:
            self.start_of_day_balance = balance
            self._day_anchor = now.date()
        self.peak_equity = equity if self.peak_equity is None else max(self.peak_equity, equity)

    def update_trade_outcome(self, pnl: float) -> None:
        self.realized_trading_profit += pnl
        if pnl < 0:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        else:
            self.consecutive_losses = 0
            self.consecutive_wins += 1

    def calculate_lot_percent(
        self,
        symbol: str,
        equity: float,
        risk_pct: float,
        sl_distance_price: float,
        tick_size: float | None = None,
        tick_value: float | None = None,
        confidence_multiplier: float = 1.0,
    ) -> float:
        """
        v19 STANDARD $200 STARTER SIZING
        Optimized for small accounts on Exness Standard.
        """
        if sl_distance_price <= 0: return 0.01
        s_cfg = self.symbols_config.get(symbol, next(iter(self.symbols_config.values())))

        # --- v19 SMALL ACCOUNT OVERDRIVE ---
        # Starting with 0.02 Lot (Safe for $200)
        # Increase 0.01 Lot for every $100 Profit
        base_lot = 0.02
        
        if self.realized_trading_profit < 2000.0:
            # Phase 1: Growth from small base
            num_increments = int(self.realized_trading_profit / 100.0)
            calculated_lot = base_lot + (num_increments * 0.01)
        else:
            # Phase 2: Overdrive (Profit > $2000)
            calculated_lot = 0.2 + (int((self.realized_trading_profit - 2000) / 100) * 0.02)

        # Win Streak Cap Protection
        max_risk_pct = 4.0 
        risk_amount = float(equity) * (max_risk_pct / 100.0)
        ts = float(tick_size or s_cfg.get("point", 0.01))
        tv = float(tick_value or (s_cfg.get("contract_size", 100) * ts))
        max_allowed_lot = risk_amount / ((sl_distance_price / ts) * tv)

        final_lot = min(calculated_lot, max_allowed_lot)
        
        step = float(s_cfg.get("lot_step", 0.01))
        final_lot = (final_lot // step) * step
        
        return round(max(0.01, min(100.0, final_lot)), 2)

    def calculate_lot(self, *args, **kwargs):
        return self.calculate_lot_percent(*args, risk_pct=3.0, **kwargs)

    def check_correlation(self, symbol: str, open_positions: list[dict[str, Any]]) -> RiskDecision:
        if len(open_positions) >= 2: return RiskDecision(False, "Overdrive Cap")
        return RiskDecision(True)

    def total_drawdown_pct(self, equity: float) -> float:
        if not self.peak_equity: return 0.0
        return max(0.0, ((self.peak_equity - equity) / self.peak_equity) * 100)

    def check_daily_dd(self, equity: float) -> RiskDecision:
        if not self.start_of_day_balance: return RiskDecision(True)
        dd = ((self.start_of_day_balance - equity) / self.start_of_day_balance) * 100
        if dd >= 15.0: return RiskDecision(False, f"Daily limit: {dd:.1f}%")
        return RiskDecision(True)

    def check_total_dd(self, equity: float) -> RiskDecision:
        dd = self.total_drawdown_pct(equity)
        if dd >= 40.0: return RiskDecision(False, f"Safety Halt: {dd:.1f}%")
        return RiskDecision(True)

    def check_spread(self, spread_points: float) -> RiskDecision:
        return RiskDecision(True)

    def news_filter(self, now_utc: datetime, news_cfg: dict[str, Any]) -> RiskDecision:
        return RiskDecision(True)

    def is_paused_by_circuit_breaker(self, equity: float) -> RiskDecision:
        return self.check_total_dd(equity)

    def breakeven_price(self, entry_price: float, sl_price: float, action: str) -> float:
        dist = abs(entry_price - sl_price)
        if action.upper() == "BUY": return entry_price + dist
        return entry_price - dist

    def trailing_stop_price(self, current_price: float, atr_value: float, action: str) -> float:
        m = 1.5
        if action.upper() == "BUY": return current_price - (atr_value * m)
        return current_price + (atr_value * m)
