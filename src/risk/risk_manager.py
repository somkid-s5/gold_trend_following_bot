from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
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

    # FIXED: 4
    def calculate_lot(
        self,
        symbol: str = "XAUUSD",
        equity: float = 0.0,
        risk_pct: float = 0.0,
        sl_distance_price: float = 0.0,
        tick_size: float | None = None,
        tick_value: float | None = None,
        confidence_multiplier: float = 1.0,
    ) -> float:
        """
        🌌 TITAN SINGULARITY SCALING (Full Real-time Compounding)
        No deltas, no buffers. Every cent of equity is used for risk calculation.
        """
        if sl_distance_price <= 0: return 0.01
        s_cfg = self.symbols_config.get(symbol, {})
        if not isinstance(s_cfg, dict) or not s_cfg:
            s_cfg = next(iter(self.symbols_config.values()), {})

        # 1. SINGULARITY CALCULATION: Pure Equity Risk
        risk_amount = float(equity) * (float(risk_pct) / 100.0)
        ts = float(tick_size or s_cfg.get("point", 0.01))
        tv = float(tick_value or (s_cfg.get("contract_size", 100) * ts))
        
        # Exact lot for the risk amount
        raw_lot = risk_amount / ((sl_distance_price / ts) * tv)

        # 2. WIN STREAK OVERDRIVE (v20+)
        if self.consecutive_wins >= 2:
            raw_lot *= 1.5

        step = float(s_cfg.get("lot_step", 0.01))
        final_lot = (raw_lot // step) * step
        
        return round(max(0.01, min(100.0, final_lot)), 2)

    def check_correlation(self, symbol: str, open_positions: list[dict[str, Any]]) -> RiskDecision:
        groups = {"USD": ["XAUUSDm", "GBPUSDm", "EURUSDm"]}
        open_syms = [pos.get("symbol", "") for pos in open_positions]
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

    # FIXED: 2
    def news_filter(self, now_utc: datetime, news_cfg: dict[str, Any]) -> RiskDecision:
        if not news_cfg.get("enabled", False):
            return RiskDecision(True)
            
        minutes_before = news_cfg.get("minutes_before", 60)
        minutes_after = news_cfg.get("minutes_after", 60)
        
        for event_str in news_cfg.get("high_impact_events", []):
            try:
                event_time = datetime.fromisoformat(event_str)
                start_window = event_time - timedelta(minutes=minutes_before)
                end_window = event_time + timedelta(minutes=minutes_after)
                
                if start_window <= now_utc <= end_window:
                    return RiskDecision(False, f"News window blocked: {event_str}")
            except ValueError:
                pass
                
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

    def sync_from_history(self, deals_df: pd.DataFrame) -> None:
        """
        Synchronize risk state from closed trade history.
        Ensures Titan v19 lot scaling persists across restarts.
        """
        if deals_df.empty:
            return
            
        # 1. Update realized profit
        self.realized_trading_profit = float(deals_df["pnl"].sum())
        
        # 2. Update streaks from the last sequence
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        
        # Sort by time to get the latest streak
        sorted_deals = deals_df.sort_values("time")
        last_trades = sorted_deals["pnl"].tolist()
        
        if not last_trades:
            return
            
        # Find current streak
        last_pnl = last_trades[-1]
        is_win_streak = last_pnl > 0
        
        for pnl in reversed(last_trades):
            if is_win_streak:
                if pnl > 0:
                    self.consecutive_wins += 1
                else:
                    break
            else:
                if pnl < 0:
                    self.consecutive_losses += 1
                else:
                    break

    def get_total_invested_capital(self) -> float:
        # This will be overridden or called by the connector in live mode
        return 0.0 
