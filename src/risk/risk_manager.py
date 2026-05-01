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

    def calculate_lot(
        self,
        symbol: str,
        equity: float,
        risk_pct: float, # This is still here for fallback, but we prioritize config logic
        sl_distance_price: float,
        tick_size: float | None = None,
        tick_value: float | None = None,
        confidence_multiplier: float = 1.0,
    ) -> float:
        """
        🚀 UNIFIED PRODUCTION SCALING (v19 TITAN OVERDRIVE)
        This same logic is used in BOTH Backtest and Live modes.
        """
        if sl_distance_price <= 0: return 0.01
        s_cfg = self.symbols_config.get(symbol, next(iter(self.symbols_config.values())))

        # 1. FIXED RATIO SCALING LOGIC
        base_lot = 0.05
        # Scaling speed from config or default $1000
        profit_delta = float(self.config.get("scaling_delta", 1000.0))
        
        num_increments = int(self.realized_trading_profit / profit_delta)
        scaled_lot = base_lot + (num_increments * 0.05)

        # 2. HARD RISK CAP (Safety First - Max 4% per trade)
        max_risk_pct = 4.0 
        risk_amount = float(equity) * (max_risk_pct / 100.0)
        ts = float(tick_size or s_cfg.get("point", 0.01))
        tv = float(tick_value or (s_cfg.get("contract_size", 100) * ts))
        max_allowed_lot = risk_amount / ((sl_distance_price / ts) * tv)

        # Use the safer (smaller) lot size
        final_lot = min(scaled_lot, max_allowed_lot)
        
        # 3. WIN STREAK BOOST
        if self.consecutive_wins >= 2:
            final_lot = min(final_lot * 1.5, max_allowed_lot)

        step = float(s_cfg.get("lot_step", 0.01))
        final_lot = (final_lot // step) * step
        
        return round(max(0.01, min(50.0, final_lot)), 2)

    def check_correlation(self, symbol: str, open_positions: list[dict[str, Any]]) -> RiskDecision:
        groups = {"USD": ["XAUUSDm", "GBPUSDm", "EURUSDm"]}
        open_syms = [pos["symbol"] for pos in open_positions]
        count = sum(1 for s in open_syms if s in groups["USD"])
        if count >= 2: return RiskDecision(False, "Correlation Limit")
        return RiskDecision(True)

    def total_drawdown_pct(self, equity: float) -> float:
        if not self.peak_equity: return 0.0
        return max(0.0, ((self.peak_equity - equity) / self.peak_equity) * 100)

    def check_daily_dd(self, equity: float) -> RiskDecision:
        threshold = float(self.config.get("max_daily_loss_pct", 10.0))
        if not self.start_of_day_balance: return RiskDecision(True)
        dd = ((self.start_of_day_balance - equity) / self.start_of_day_balance) * 100
        if dd >= threshold: return RiskDecision(False, f"Daily limit: {dd:.1f}%")
        return RiskDecision(True)

    def check_total_dd(self, equity: float) -> RiskDecision:
        threshold = float(self.config.get("max_total_drawdown_pct", 50.0))
        dd = self.total_drawdown_pct(equity)
        if dd >= threshold: return RiskDecision(False, f"Global Halt: {dd:.1f}%")
        return RiskDecision(True)

    def check_spread(self, spread_points: float) -> RiskDecision:
        max_s = float(self.config.get("max_spread_points", 500))
        if spread_points > max_s: return RiskDecision(False, f"Spread: {spread_points:.1f}")
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

    def get_total_invested_capital(self) -> float:
        # This will be overridden or called by the connector in live mode
        return 0.0 
