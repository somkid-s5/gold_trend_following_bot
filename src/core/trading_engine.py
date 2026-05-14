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
        self.equity_history: list[dict[str, Any]] = []
        self._load_existing_history()
        
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
            current_volume = float(position["volume"])
            ticket = int(position["ticket"])
            
            # Smart Exit Logic from ExitManager (v20)
            risk_dist = abs(entry_price - current_sl) if current_sl > 0 else (atr_value * 2.5)
            
            instruction = self.exit_manager.calculate_v20_managed_exit(
                action=action,
                entry=entry_price,
                current_sl=current_sl,
                current_price=current_price,
                risk_dist=risk_dist,
                point=point,
                config=self.config["risk"]
            )

            # 1. Handle Partial Close
            comment = position.get("comment", "")
            if instruction.partial_close_pct > 0 and "partial" not in comment:
                close_vol = round(current_volume * instruction.partial_close_pct, 2)
                if close_vol >= 0.01:
                    self.connector.close_partial_position(ticket, close_vol)
                    results.append(EngineResult(strategy_name, "partial_close", f"Closed {close_vol} for {symbol} ticket {ticket} ({instruction.reason})"))

            # 2. Handle SL Update
            if abs(instruction.new_sl - current_sl) >= point:
                self.connector.modify_position(ticket, sl=instruction.new_sl, tp=current_tp)
                results.append(EngineResult(strategy_name, "managed", f"Updated SL for {symbol} ticket {ticket}: {instruction.reason}"))
        return results

    # FIXED: 3
    def run(self, symbol: str, strategy_name: str) -> list[EngineResult]:
        try:
            guard_path = self.config.get("operational_guards", {}).get("guard_report_path")
            if guard_path:
                guard_status = self.guard_evaluator.load_guard_file(guard_path)
                if guard_status and guard_status.status == "PAUSE":
                    return [EngineResult(strategy_name, "paused", "Operational guard requested pause")]

            balance, equity = self._live_account_state()
            now_utc = datetime.now(timezone.utc)
            results: list[EngineResult] = []
            
            strategy = self.strategies[strategy_name]
            history_count = int(self.config["trading"]["history_bars"].get(strategy_name, 1500))
            frame = self.data_handler.get_live_bars(symbol, strategy.timeframe, history_count)
            
            if frame.empty: 
                self.logger.warning("DATA ERROR   | %s: No bars returned", symbol)
                return []
            
            # 1. Position Management
            results.extend(self._manage_open_positions(symbol, frame, strategy_name))

            # 2. Risk & Market Condition Check
            all_open = self.connector.get_positions()
            corr_decision = self.risk_manager.check_correlation(symbol, all_open)
            if not corr_decision.allowed:
                self.logger.info("SKIP %s | %s", symbol, corr_decision.reason)
                return results

            symbol_info = self.connector.get_symbol_info(symbol)
            tick = self.connector.get_symbol_tick(symbol)
            spread = (float(tick.ask) - float(tick.bid)) / (float(symbol_info.point) or 0.01)
            
            self.logger.info("SCANNING     | %s | Price: %.2f | Spread: %.1f", symbol, frame["close"].iloc[-1], spread)
            
            decision = self._passes_risk(spread, now_utc, equity)
            if not decision.allowed:
                self.logger.info("RISK BLOCK   | %s: %s", symbol, decision.reason)
                return results

            # 3. Execution Check
            existing = self._strategy_positions(symbol, strategy_name)
            if len(existing) >= int(self.config["risk"]["allow_strategy_addons"].get(strategy_name, 1)):
                return results

            signals = strategy.generate_signals(frame, {"symbol": symbol})
            if signals:
                best = max(signals, key=lambda x: x.confidence)
                results.append(self._execute_signal(symbol, best, equity))
            
            self._update_runtime_status(symbol, balance, equity, len(existing), [r.details for r in results])
            return results

        except Exception as exc:
            self.logger.error("CRITICAL RUN ERROR: %s", exc, exc_info=True)
            return [EngineResult(strategy_name, "error", str(exc))]

    def is_market_open(self, now_utc: datetime) -> bool:
        """
        ตรวจสอบว่าตลาดทองคำ (XAUUSD) เปิดอยู่หรือไม่
        โดยปกติ: เปิดวันจันทร์ 01:00 UTC - ปิดวันศาร์ 23:59 UTC (เช้าวันเสาร์ 00:00)
        """
        weekday = now_utc.weekday() # 0=Monday, 6=Sunday
        hour = now_utc.hour

        # วันเสาร์ (5): ปิดตั้งแต่ 00:00 UTC เป็นต้นไป
        if weekday == 5:
            return False
        # วันอาทิตย์ (6): ปิดทั้งวัน
        if weekday == 6:
            return False
        # วันจันทร์ (0): เปิดตั้งแต่ 01:00 UTC เป็นต้นไป (เช็คเผื่อบางโบรกเปิดช้า)
        if weekday == 0 and hour < 1:
            return False
            
        return True

    def run_portfolio(self) -> list[EngineResult]:
        if self.mode != "live" or self.connector is None:
            raise ValueError("run_portfolio is for live mode with connector only")

        try:
            now_utc = datetime.now(timezone.utc)
            
            # --- MARKET OPEN GUARD ---
            if not self.is_market_open(now_utc):
                self.logger.info("MARKET CLOSED | System sleeping until Monday... 😴")
                return [EngineResult("system", "idle", "Market is closed")]

            balance, equity = self._live_account_state()
            results: list[EngineResult] = []
            
            self.logger.info("=" * 60)
            self.logger.info("PORTFOLIO STATUS | %s", now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"))
            self.logger.info("ACCOUNT          | Bal: %.2f | Eq: %.2f", balance, equity)
            self.logger.info("-" * 60)

            symbol_list = list(self.config.get("symbols", {}).keys())
            for symbol in symbol_list:
                for name in self.strategies:
                    # Sync risk stats from history before running
                    trades_df = self.connector.get_strategy_closed_trades(
                        symbol=symbol,
                        strategy_name=name,
                        lookback_days=30
                    )
                    self.risk_manager.sync_from_history(trades_df)
                    
                    # FIXED: 3
                    results.extend(self.run(symbol, name))
            
            # Final update for portfolio state
            self._update_runtime_status("PORTFOLIO", balance, equity, len(self.connector.get_positions()), [r.details for r in results])
            self._update_trade_history()
            self._update_guard_status()
            return results

        except Exception as exc:
            self.logger.error("CRITICAL PORTFOLIO ERROR: %s", exc, exc_info=True)
            return [EngineResult("system", "error", str(exc))]

    def _load_existing_history(self) -> None:
        try:
            status_path = Path(self.config.get("reports_dir", "reports")) / "runtime_status.json"
            if status_path.exists():
                data = json.loads(status_path.read_text(encoding="utf-8"))
                self.equity_history = data.get("equity_history", [])[-100:]
        except:
            self.equity_history = []

    def _update_runtime_status(self, symbol: str, balance: float, equity: float, open_positions: int, details: list[str]) -> None:
        try:
            # Update equity history buffer
            now_iso = datetime.now(timezone.utc).isoformat()
            self.equity_history.append({
                "time": now_iso,
                "equity": round(equity, 2),
                "balance": round(balance, 2)
            })
            if len(self.equity_history) > 100:
                self.equity_history.pop(0)

            status_path = Path(self.config.get("reports_dir", "reports")) / "runtime_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            
            status_data = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "status": "running",
                "balance": round(balance, 2),
                "equity": round(equity, 2),
                "open_positions": open_positions,
                "details": details[-5:] if details else ["Scanning..."],
                "equity_history": self.equity_history
            }
            
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to update runtime status: {e}")

    def _update_trade_history(self) -> None:
        if not self.connector:
            return
        try:
            history_path = Path(self.config.get("reports_dir", "reports")) / "trade_history.json"
            
            # Fetch last 30 days of trades for the dashboard
            all_trades = []
            for symbol in self.config.get("symbols", {}):
                for strategy_name in self.strategies:
                    trades_df = self.connector.get_strategy_closed_trades(
                        symbol=symbol,
                        strategy_name=strategy_name,
                        lookback_days=30
                    )
                    if not trades_df.empty:
                        # Convert to dict format for JSON
                        for _, row in trades_df.iterrows():
                            all_trades.append({
                                "time": row["time"].isoformat(),
                                "symbol": symbol,
                                "strategy": row["strategy"],
                                "pnl": round(float(row["pnl"]), 2),
                                "balance": round(float(row["balance"]), 2)
                            })
            
            # Sort by time descending
            all_trades.sort(key=lambda x: x["time"], reverse=True)
            
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(all_trades[:50], f, indent=2) # Keep last 50 for UI
                
        except Exception as e:
            self.logger.error(f"Failed to update trade history: {e}")

    def _update_guard_status(self) -> None:
        if not self.connector:
            return
        try:
            guard_path = Path(self.config.get("reports_dir", "reports")) / "guard_status.json"
            
            # Use the first symbol and strategy to evaluate basic performance
            # In a multi-symbol setup, this could be aggregated, but for now we take the primary one
            symbol = list(self.config.get("symbols", {}).keys())[0]
            strategy_name = list(self.strategies.keys())[0]
            
            trades_df = self.connector.get_strategy_closed_trades(
                symbol=symbol,
                strategy_name=strategy_name,
                lookback_days=self.config.get("operational_guards", {}).get("evaluation_window_days", 30),
                current_balance=self.connector.get_account_info().balance
            )
            
            guard_result = self.guard_evaluator.evaluate_trade_frame(trades_df)
            
            payload = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "status": guard_result.status,
                "reasons": guard_result.reasons,
                "metrics": guard_result.metrics
            }
            
            with open(guard_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to update guard status: {e}")

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
