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
from src.strategies import Signal, Strategy
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
        self.news_calendar = NewsCalendar(config["news_filter"])
        self.guard_evaluator = OperationalGuardEvaluator(config.get("operational_guards", {}))
        self.notifier = notifier

    def _live_account_state(self) -> tuple[float, float]:
        if self.connector is None:
            raise ValueError("Live mode requires MT5Connector")
        snapshot = self.connector.get_account_info()
        self.risk_manager.update_equity_state(snapshot.balance, snapshot.equity)
        
        # Update trade outcomes from history to sync consecutive losses
        strategy_name = self.config.get("forward_test", {}).get("strategy", "trend_following")
        try:
            history = self.connector.get_strategy_closed_trades(
                symbol=self.config["trading"]["symbol"],
                strategy_name=strategy_name,
                lookback_days=1,
                current_balance=snapshot.balance
            )
            if not history.empty and "pnl" in history.columns:
                # Sort by time and update outcome for the last trade
                last_trade_pnl = float(history.iloc[-1]["pnl"])
                self.risk_manager.update_trade_outcome(last_trade_pnl)
        except Exception as exc:
            self.logger.warning("Failed to sync trade history: %s", exc)

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
        if self.connector is None:
            return []
        positions = self.connector.get_positions(symbol)
        return [pos for pos in positions if strategy_name in pos.get("comment", "")]

    def _refresh_news_events(self) -> None:
        try:
            self.config["news_filter"]["resolved_events"] = self.news_calendar.get_events()
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            self.logger.warning("News event refresh failed: %s", exc)

    def _close_all_positions(self, symbol: str) -> list[EngineResult]:
        if self.connector is None:
            return []
        results: list[EngineResult] = []
        for position in self.connector.get_positions(symbol):
            ticket = int(position["ticket"])
            self.connector.close_position(ticket)
            strategy = position.get("comment", "portfolio_guard")
            results.append(EngineResult(strategy, "closed", f"Closed ticket {ticket} after risk breach"))
        return results

    def _write_runtime_status(self, payload: dict[str, Any]) -> None:
        runtime_cfg = self.config.get("runtime", {})
        if not runtime_cfg.get("write_heartbeat", False):
            return
        output_path = Path(runtime_cfg.get("heartbeat_path", "reports/runtime_status.json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _refresh_operational_guard_report(self, symbol: str, balance: float) -> None:
        guard_cfg = self.config.get("operational_guards", {})
        if not guard_cfg.get("enabled", False) or self.connector is None:
            return
        strategy_name = self.config.get("forward_test", {}).get("strategy", "trend_following")
        trades = self.connector.get_strategy_closed_trades(
            symbol=symbol,
            strategy_name=strategy_name,
            lookback_days=int(guard_cfg.get("lookback_days", 365)),
            current_balance=balance,
        )
        status = self.guard_evaluator.evaluate_trade_frame(trades, base_balance=balance)
        output_path = Path(guard_cfg.get("guard_report_path", "reports/guard_status.json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": status.status,
            "reasons": status.reasons,
            "metrics": status.metrics,
            "source": "mt5_history_auto",
            "strategy": strategy_name,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _check_operational_pause(self, symbol: str) -> list[EngineResult]:
        guard_cfg = self.config.get("operational_guards", {})
        if not guard_cfg.get("enabled", False):
            return []
        guard_path = guard_cfg.get("guard_report_path")
        if not guard_path:
            return []
        status = self.guard_evaluator.load_guard_file(Path(guard_path))
        if status is None or status.status != "PAUSE":
            return []

        results = [EngineResult("portfolio", "paused", "; ".join(status.reasons))]
        if guard_cfg.get("close_positions_on_trigger", False):
            results.extend(self._close_all_positions(symbol))
        return results

    def _load_guard_payload(self) -> dict[str, Any] | None:
        guard_path = self.config.get("operational_guards", {}).get("guard_report_path")
        if not guard_path:
            return None
        path = Path(guard_path)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _maybe_send_guard_alert(self, guard_payload: dict[str, Any] | None) -> None:
        if self.notifier is None or not self.notifier.is_enabled():
            return
        tg_cfg = self.config.get("notifications", {}).get("telegram", {})
        if not tg_cfg.get("send_guard_alerts", True) or not guard_payload:
            return
        state = self.notifier.load_state()
        guard_status = guard_payload.get("status")
        if guard_status == "PAUSE" and state.get("last_guard_alert_status") != "PAUSE":
            text = self.notifier.build_event_message(
                "Guard Alert",
                datetime.now(timezone.utc),
                f"สถานะ PAUSE | เหตุผล: {', '.join(guard_payload.get('reasons', []))}"
            )
            self.notifier.send_message(text)
            state["last_guard_alert_status"] = "PAUSE"
            self.notifier.save_state(state)
        elif guard_status == "OK" and state.get("last_guard_alert_status") == "PAUSE":
            state["last_guard_alert_status"] = "OK"
            self.notifier.save_state(state)

    def _maybe_send_daily_summary(self, symbol: str, balance: float, equity: float, now_utc: datetime) -> None:
        if self.notifier is None or not self.notifier.should_send_daily_summary(now_utc):
            return
        if self.connector is None:
            return
        strategy_name = self.config.get("forward_test", {}).get("strategy", "trend_following")
        trades = self.connector.get_strategy_closed_trades(
            symbol=symbol,
            strategy_name=strategy_name,
            lookback_days=2,
            current_balance=balance,
        )
        if not trades.empty:
            trades = trades.loc[trades["time"].dt.date == now_utc.date()].copy()
        guard_payload = self._load_guard_payload()
        text = self.notifier.build_daily_summary(
            strategy_name=strategy_name,
            now_utc=now_utc,
            account={"balance": balance, "equity": equity},
            guard_payload=guard_payload,
            trades_frame=trades,
        )
        self.notifier.send_message(text)
        self.notifier.mark_daily_summary_sent(now_utc)

    def _manage_open_positions(self, symbol: str, frame: pd.DataFrame, strategy_name: str) -> list[EngineResult]:
        if self.connector is None:
            return []
        positions = self._strategy_positions(symbol, strategy_name)
        if not positions:
            return []

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
            breakeven_trigger = self.risk_manager.breakeven_price(entry_price, current_sl, action)
            move_to_be = current_price >= breakeven_trigger if action == "BUY" else current_price <= breakeven_trigger
            new_sl = current_sl

            if move_to_be:
                new_sl = max(current_sl, entry_price) if action == "BUY" else min(current_sl, entry_price)

            trailing_candidate = self.risk_manager.trailing_stop_price(current_price, atr_value, action)
            if action == "BUY" and trailing_candidate > new_sl + point:
                new_sl = trailing_candidate
            if action == "SELL" and (new_sl == 0 or trailing_candidate < new_sl - point):
                new_sl = trailing_candidate

            if abs(new_sl - current_sl) >= point:
                self.connector.modify_position(int(position["ticket"]), sl=new_sl, tp=current_tp)
                results.append(
                    EngineResult(
                        strategy_name,
                        "managed",
                        f"Updated SL for ticket {position['ticket']} to {new_sl:.2f}",
                    )
                )

        return results

    def _is_new_bar(self, strategy_name: str, frame: pd.DataFrame) -> bool:
        current = frame.iloc[-1]["time"]
        previous = self.last_bar_time.get(strategy_name)
        if previous is not None and current <= previous:
            return False
        self.last_bar_time[strategy_name] = current
        return True

    def _execute_signal(self, symbol: str, signal: Signal, equity: float) -> EngineResult:
        if self.connector is None:
            raise ValueError("Signal execution requires MT5Connector")
        symbol_info = self.connector.get_symbol_info(symbol)
        sl_distance = abs(signal.entry - signal.sl)
        lot = self.risk_manager.calculate_lot(
            equity=equity,
            risk_pct=float(self.config["risk"]["risk_per_trade_pct"]),
            sl_distance_price=sl_distance,
            tick_size=float(symbol_info.trade_tick_size or symbol_info.point),
            tick_value=float(symbol_info.trade_tick_value or (symbol_info.contract_size * symbol_info.point)),
            confidence_multiplier=signal.confidence,
        )
        result = self.connector.send_order(
            symbol=symbol,
            action=signal.action,
            volume=lot,
            sl=signal.sl,
            tp=signal.tp,
            comment=f"{signal.strategy}|conf={signal.confidence:.2f}",
        )
        self.logger.info("Order sent: %s", result)
        return EngineResult(signal.strategy, "executed", f"{signal.action} {lot} lots")

    def run(self, symbol: str, strategy_name: str | None = None) -> list[EngineResult]:
        """Main execution loop for live trading."""
        if self.mode != "live":
            raise ValueError("TradingEngine.run is for live mode only")

        try:
            balance, equity = self._live_account_state()
            now_utc = datetime.now(timezone.utc)
            results: list[EngineResult] = []
            
            # --- PRODUCTION DASHBOARD ---
            daily_dd = self.risk_manager.daily_drawdown_pct(equity)
            total_dd = self.risk_manager.total_drawdown_pct(equity)
            streak = self.risk_manager.consecutive_losses
            
            self.logger.info("=" * 60)
            self.logger.info("LIVE STATUS | %s | %s", symbol.upper(), now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"))
            self.logger.info("ACCOUNT     | Bal: %.2f | Eq: %.2f | DD: %.2f%%", balance, equity, total_dd)
            self.logger.info("RISK        | Daily Loss: %.2f%% | Streak: %d", daily_dd, streak)
            self.logger.info("-" * 60)

            self._refresh_news_events()
            
            # Check for operational pauses (Guards or Circuit Breaker)
            pause_results = self._check_operational_pause(symbol)
            if pause_results:
                self._maybe_send_guard_alert(self._load_guard_payload())
                self._write_runtime_status({"status": "paused", "equity": equity, "balance": balance})
                return pause_results

            # Check Global Risk Limits
            daily_guard = self.risk_manager.check_daily_dd(equity)
            total_guard = self.risk_manager.check_total_dd(equity)
            if not daily_guard.allowed or not total_guard.allowed:
                reason = daily_guard.reason if not daily_guard.allowed else total_guard.reason
                self.logger.warning("RISK LIMIT BREACHED: %s", reason)
                if self.config["risk"].get("close_all_on_daily_limit", False):
                    results.extend(self._close_all_positions(symbol))
                return results

            # Run Strategies
            for name, strategy in self.strategies.items():
                if strategy_name and name != strategy_name:
                    continue

                history_count = int(self.config["trading"]["history_bars"][name])
                frame = self.data_handler.get_live_bars(symbol, strategy.timeframe, history_count)
                
                if not self._is_new_bar(name, frame):
                    continue

                # Position Management (Trailing SL, etc.)
                frame_for_management = frame.copy()
                frame_for_management["atr"] = atr(frame_for_management, 14)
                results.extend(self._manage_open_positions(symbol, frame_for_management, name))

                # Market Conditions
                symbol_info = self.connector.get_symbol_info(symbol)
                tick = self.connector.get_symbol_tick(symbol)
                spread_points = (float(tick.ask) - float(tick.bid)) / float(symbol_info.point or 0.01)
                
                existing_positions = self._strategy_positions(symbol, name)
                max_pos = int(self.config["risk"]["allow_strategy_addons"].get(name, 1))
                
                last_price = float(frame["close"].iloc[-1])
                self.logger.info("SCANNING    | %s | Price: %.2f | Spr: %.1f | Pos: %d/%d", 
                                 name.upper(), last_price, spread_points, len(existing_positions), max_pos)

                # Final Risk Check before Signal Generation
                decision = self._passes_risk(spread_points, now_utc, equity)
                if not decision.allowed:
                    self.logger.info("FILTERED    | %s", decision.reason)
                    continue

                if len(existing_positions) >= max_pos:
                    continue

                # Signal Execution
                signals = strategy.generate_signals(frame, {})
                if signals:
                    best_signal = max(signals, key=lambda item: item.confidence)
                    results.append(self._execute_signal(symbol, best_signal, equity))
                else:
                    self.logger.info("IDLE        | %s: No signal", name.upper())

            self._write_runtime_status({"status": "running", "equity": equity, "balance": balance})
            return results

        except Exception as exc:
            self.logger.error("CRITICAL ERROR in Live Loop: %s", exc, exc_info=True)
            return [EngineResult("system", "error", str(exc))]
