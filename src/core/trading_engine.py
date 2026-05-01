from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.broker.mt5_connector import MT5Connector
from src.data.data_handler import DataHandler
from src.data.news_calendar import NewsCalendar
from src.core.operational_guards import OperationalGuardEvaluator
from src.risk.risk_manager import RiskDecision, RiskManager
from src.strategies import Signal, Strategy, atr
from src.utils.telegram_notifier import TelegramNotifier


@dataclass(slots=True)
class EngineResult:
    strategy: str
    status: str
    details: str


class TradingEngine:
    def __init__(
        self,
        connector: MT5Connector | None,
        data_handler: DataHandler,
        risk_manager: RiskManager,
        strategies: dict[str, Strategy],
        config: dict[str, Any],
        logger: Any,
        mode: str = "live",
        notifier: TelegramNotifier | None = None,
    ) -> None:
        self.connector = connector
        self.data_handler = data_handler
        self.risk_manager = risk_manager
        self.strategies = strategies
        self.config = config
        self.logger = logger
        self.mode = mode
        self.last_bar_time: dict[str, pd.Timestamp] = {}
        
        news_cfg = config.get("news_filter", {"enabled": False, "high_impact_events": []})
        self.news_calendar = NewsCalendar(news_cfg)
        self.guard_evaluator = OperationalGuardEvaluator(config.get("operational_guards", {}))
        self.notifier = notifier

    def _live_account_state(self) -> tuple[float, float]:
        if self.connector is None:
            raise ValueError("Live mode requires MT5Connector")
        snapshot = self.connector.get_account_info()
        self.risk_manager.update_equity_state(snapshot.balance, snapshot.equity)
        return snapshot.balance, snapshot.equity

    def _passes_risk(self, spread_points: float, now_utc: datetime, equity: float) -> RiskDecision:
        for decision in (
            self.risk_manager.check_daily_dd(equity),
            self.risk_manager.check_total_dd(equity),
            self.risk_manager.check_spread(spread_points),
            self.risk_manager.news_filter(now_utc, self.config["news_filter"]),
            self.risk_manager.is_paused_by_circuit_breaker(equity),
        ):
            if not decision.allowed:
                return decision
        return RiskDecision(True)

    def _strategy_positions(self, symbol: str, strategy_name: str) -> list[dict[str, Any]]:
        if self.connector is None: return []
        positions = self.connector.get_positions(symbol)
        return [pos for pos in positions if strategy_name in pos.get("comment", "")]

    def _manage_open_positions(self, symbol: str, frame: pd.DataFrame, strategy_name: str) -> list[EngineResult]:
        if self.connector is None: return []
        positions = self._strategy_positions(symbol, strategy_name)
        if not positions: return []

        atr_series = frame.get("atr")
        atr_value = float(atr_series.iloc[-1]) if atr_series is not None else float(frame["high"].iloc[-1] - frame["low"].iloc[-1])
        tick = self.connector.get_symbol_tick(symbol)
        point = float(self.connector.get_symbol_info(symbol).point or 0.01)
        results: list[EngineResult] = []

        for position in positions:
            action = "BUY" if int(position["type"]) == 0 else "SELL"
            current_price = float(tick.bid if action == "BUY" else tick.ask)
            entry_price = float(position["price_open"])
            current_sl = float(position["sl"])
            current_tp = float(position["tp"])
            
            # Smart Exit Logic from v3
            risk_dist = abs(entry_price - current_sl) if current_sl > 0 else (atr_value * 2.0)
            be_trigger = entry_price + (risk_dist * 1.5) if action == "BUY" else entry_price - (risk_dist * 1.5)
            
            new_sl = current_sl
            if (action == "BUY" and current_price >= be_trigger) or (action == "SELL" and current_price <= be_trigger):
                new_sl = max(current_sl, entry_price) if action == "BUY" else min(current_sl, entry_price)

            if abs(new_sl - current_sl) >= point:
                self.connector.modify_position(int(position["ticket"]), sl=new_sl, tp=current_tp)
                results.append(EngineResult(strategy_name, "managed", f"Updated SL for {symbol} ticket {position['ticket']}"))
        return results

    def run_portfolio(self) -> list[EngineResult]:
        if self.mode != "live" or self.connector is None:
            raise ValueError("run_portfolio is for live mode with connector only")

        try:
            balance, equity = self._live_account_state()
            now_utc = datetime.now(timezone.utc)
            results: list[EngineResult] = []
            
            self.logger.info("=" * 60)
            self.logger.info("PORTFOLIO STATUS | %s", now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"))
            self.logger.info("ACCOUNT          | Bal: %.2f | Eq: %.2f", balance, equity)
            self.logger.info("-" * 60)

            symbol_list = list(self.config.get("symbols", {}).keys())
            for symbol in symbol_list:
                for name, strategy in self.strategies.items():
                    history_count = int(self.config["trading"]["history_bars"].get(name, 1500))
                    frame = self.data_handler.get_live_bars(symbol, strategy.timeframe, history_count)
                    
                    if frame.empty: 
                        self.logger.warning("DATA ERROR   | %s: No bars returned", symbol)
                        continue
                    
                    # 1. Position Management
                    results.extend(self._manage_open_positions(symbol, frame, name))

                    # 2. Risk & Market Condition Check
                    all_open = self.connector.get_positions()
                    corr_decision = self.risk_manager.check_correlation(symbol, all_open)
                    if not corr_decision.allowed:
                        self.logger.info("SKIP %s | %s", symbol, corr_decision.reason)
                        continue

                    symbol_info = self.connector.get_symbol_info(symbol)
                    tick = self.connector.get_symbol_tick(symbol)
                    spread = (float(tick.ask) - float(tick.bid)) / (float(symbol_info.point) or 0.01)
                    
                    self.logger.info("SCANNING     | %s | Price: %.2f | Spread: %.1f", symbol, frame["close"].iloc[-1], spread)
                    
                    decision = self._passes_risk(spread, now_utc, equity)
                    if not decision.allowed:
                        self.logger.info("RISK BLOCK   | %s: %s", symbol, decision.reason)
                        continue

                    # 3. Execution Check
                    existing = self._strategy_positions(symbol, name)
                    if len(existing) >= int(self.config["risk"]["allow_strategy_addons"].get(name, 1)):
                        continue

                    signals = strategy.generate_signals(frame, {"symbol": symbol})
                    if signals:
                        best = max(signals, key=lambda x: x.confidence)
                        results.append(self._execute_signal(symbol, best, equity))
                        balance, equity = self._live_account_state() 
            
            return results

        except Exception as exc:
            self.logger.error("CRITICAL PORTFOLIO ERROR: %s", exc, exc_info=True)
            return [EngineResult("system", "error", str(exc))]

    def _execute_signal(self, symbol: str, signal: Signal, equity: float) -> EngineResult:
        symbol_info = self.connector.get_symbol_info(symbol)
        sl_distance = abs(signal.entry - signal.sl)
        lot = self.risk_manager.calculate_lot(
            symbol=symbol,
            equity=equity,
            risk_pct=float(self.config["risk"]["risk_per_trade_pct"]),
            sl_distance_price=sl_distance,
            tick_size=float(symbol_info.trade_tick_size or symbol_info.point),
            tick_value=float(symbol_info.trade_tick_value or (symbol_info.contract_size * symbol_info.point)),  
            confidence_multiplier=signal.confidence,
        )
        self.connector.send_order(
            symbol=symbol,
            action=signal.action,
            volume=lot,
            sl=signal.sl,
            tp=signal.tp,
            comment=f"{signal.strategy}|conf={signal.confidence:.2f}",
        )
        
        # --- TELEGRAM NOTIFICATION ---
        if self.notifier and self.notifier.is_enabled():
            msg = (
                f"🚀 *ORDER EXECUTED*\n"
                f"🌍 Symbol: `{symbol}`\n"
                f"🎯 Action: `{signal.action}`\n"
                f"💰 Volume: `{lot} lots`\n"
                f"🛡️ SL: `{signal.sl:.2f}`\n"
                f"🏁 TP: `{signal.tp:.2f}`\n"
                f"📈 Confidence: `{signal.confidence:.2f}`"
            )
            self.notifier.send_message(msg)
            
        return EngineResult(signal.strategy, "executed", f"{symbol} {signal.action} {lot} lots")
