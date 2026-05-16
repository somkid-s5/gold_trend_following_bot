from __future__ import annotations

import random
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.exit_logic import ExitManager
from src.core.operational_guards import OperationalGuardEvaluator
from src.risk.risk_manager import RiskManager
from src.strategies import Strategy


@dataclass(slots=True)
class BacktestTrade:
    time: pd.Timestamp
    strategy: str
    action: str
    entry: float
    exit: float
    pnl: float
    balance: float
    hold_bars: int = 1


class Backtester:
    """
    Unified Backtester — uses EXACTLY the same exit logic as Live Trading Engine:
    1. ExitManager.calculate_v20_managed_exit() for SL management & partial close
    2. Same lot calculation via RiskManager
    3. Same signal generation via Strategy.generate_signals()
    4. Spread & slippage simulation for realistic results
    5. Multi-bar position holding (positions stay open until SL/TP hit)
    """

    def __init__(
        self,
        strategy: Strategy,
        risk_manager: RiskManager,
        config: dict[str, Any],
        logger: Any,
    ) -> None:
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.config = config
        self.logger = logger
        self.exit_manager = ExitManager()
        self.guard_evaluator = OperationalGuardEvaluator(config.get("operational_guards", {}))

    def export_trades(self, trades: list[BacktestTrade], output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(
            [
                {
                    "time": trade.time,
                    "strategy": trade.strategy,
                    "action": trade.action,
                    "entry": trade.entry,
                    "exit": trade.exit,
                    "pnl": trade.pnl,
                    "balance": trade.balance,
                    "hold_bars": trade.hold_bars,
                }
                for trade in trades
            ]
        )
        frame.to_csv(path, index=False)
        return path

    def _apply_spread(self, action: str, price: float, spread_points: float, tick_size: float) -> float:
        """INFRA-1: Simulate bid/ask spread (buy at ask, sell at bid)."""
        half_spread = (spread_points * tick_size) / 2.0
        if action == "BUY":
            return price + half_spread  # Buy at ask (higher)
        else:
            return price - half_spread  # Sell at bid (lower)

    def _apply_slippage(self, price: float, max_slippage_points: float, tick_size: float) -> float:
        """INFRA-2: Simulate random slippage on entry."""
        if max_slippage_points <= 0:
            return price
        slippage = random.uniform(0, max_slippage_points) * tick_size
        # Slippage always works against the trader
        return price + slippage  # For buys it's worse; adjusted per-action in caller

    def _simulate_multi_bar_exit(
        self,
        signal_action: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        risk_dist: float,
        tick_size: float,
        tick_value: float,
        lot: float,
        fee_per_lot: float,
        spread_cost: float,
        rows: list[pd.Series],
        start_idx: int,
        max_hold_bars: int,
    ) -> tuple[float, float, int]:
        """
        INFRA-3: Hold position across multiple bars until SL/TP is hit.
        Uses v20 exit logic on each bar (same as live trading).
        Returns: (exit_price, pnl, bars_held)
        """
        current_sl = sl_price
        partial_closed = False
        partial_pnl = 0.0
        remaining_lot = lot

        for bar_offset in range(max_hold_bars):
            bar_idx = start_idx + bar_offset
            if bar_idx >= len(rows):
                break

            bar = rows[bar_idx]
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])

            # Apply v20 managed exit (same as live trading)
            best_price = high if signal_action == "BUY" else low
            instruction = self.exit_manager.calculate_v20_managed_exit(
                action=signal_action,
                entry=entry_price,
                current_sl=current_sl,
                current_price=best_price,
                risk_dist=risk_dist,
                point=tick_size,
                config=self.config["risk"],
            )

            # Update managed SL
            current_sl = instruction.new_sl

            # Simulate partial close (same as live: close 50% at RR 2.0)
            if instruction.partial_close_pct > 0 and not partial_closed:
                partial_lot = remaining_lot * instruction.partial_close_pct
                remaining_lot -= partial_lot
                if signal_action == "BUY":
                    partial_pnl = (best_price - entry_price) / tick_size * tick_value * partial_lot
                else:
                    partial_pnl = (entry_price - best_price) / tick_size * tick_value * partial_lot
                partial_closed = True

            # Check SL hit
            if signal_action == "BUY" and low <= current_sl:
                exit_price = current_sl
                remaining_pnl = (exit_price - entry_price) / tick_size * tick_value * remaining_lot
                total_pnl = partial_pnl + remaining_pnl - fee_per_lot * lot - spread_cost
                return exit_price, total_pnl, bar_offset + 1

            if signal_action == "SELL" and high >= current_sl:
                exit_price = current_sl
                remaining_pnl = (entry_price - exit_price) / tick_size * tick_value * remaining_lot
                total_pnl = partial_pnl + remaining_pnl - fee_per_lot * lot - spread_cost
                return exit_price, total_pnl, bar_offset + 1

            # Check TP hit
            if signal_action == "BUY" and high >= tp_price:
                exit_price = tp_price
                remaining_pnl = (exit_price - entry_price) / tick_size * tick_value * remaining_lot
                total_pnl = partial_pnl + remaining_pnl - fee_per_lot * lot - spread_cost
                return exit_price, total_pnl, bar_offset + 1

            if signal_action == "SELL" and low <= tp_price:
                exit_price = tp_price
                remaining_pnl = (entry_price - exit_price) / tick_size * tick_value * remaining_lot
                total_pnl = partial_pnl + remaining_pnl - fee_per_lot * lot - spread_cost
                return exit_price, total_pnl, bar_offset + 1

        # Max hold bars reached — close at last bar's close (timeout)
        exit_price = close
        if signal_action == "BUY":
            remaining_pnl = (exit_price - entry_price) / tick_size * tick_value * remaining_lot
        else:
            remaining_pnl = (entry_price - exit_price) / tick_size * tick_value * remaining_lot
        total_pnl = partial_pnl + remaining_pnl - fee_per_lot * lot - spread_cost
        return exit_price, total_pnl, max_hold_bars

    def _simulate_single_bar_exit(
        self,
        signal_action: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        risk_dist: float,
        tick_size: float,
        tick_value: float,
        lot: float,
        fee_per_lot: float,
        spread_cost: float,
        next_row: pd.Series,
    ) -> tuple[float, float]:
        """Fallback: Single-bar exit with v20 logic (for DCA mode compatibility)."""
        high = float(next_row["high"])
        low = float(next_row["low"])
        close = float(next_row["close"])

        best_price = high if signal_action == "BUY" else low
        instruction = self.exit_manager.calculate_v20_managed_exit(
            action=signal_action,
            entry=entry_price,
            current_sl=sl_price,
            current_price=best_price,
            risk_dist=risk_dist,
            point=tick_size,
            config=self.config["risk"],
        )

        managed_sl = instruction.new_sl
        partial_close_pct = instruction.partial_close_pct

        exit_price = close
        if signal_action == "BUY":
            if low <= managed_sl:
                exit_price = managed_sl
            elif high >= tp_price:
                exit_price = tp_price
        else:
            if high >= managed_sl:
                exit_price = managed_sl
            elif low <= tp_price:
                exit_price = tp_price

        if signal_action == "BUY":
            pnl = (exit_price - entry_price) / tick_size * tick_value * lot
        else:
            pnl = (entry_price - exit_price) / tick_size * tick_value * lot

        if partial_close_pct > 0 and exit_price == close:
            partial_lot = lot * partial_close_pct
            remaining_lot = lot - partial_lot
            if signal_action == "BUY":
                partial_pnl = (best_price - entry_price) / tick_size * tick_value * partial_lot
                remaining_pnl = (exit_price - entry_price) / tick_size * tick_value * remaining_lot
            else:
                partial_pnl = (entry_price - best_price) / tick_size * tick_value * partial_lot
                remaining_pnl = (entry_price - exit_price) / tick_size * tick_value * remaining_lot
            pnl = partial_pnl + remaining_pnl

        pnl -= fee_per_lot * lot + spread_cost
        return exit_price, pnl

    def run(self, frame: pd.DataFrame, initial_balance: float, symbol: str = "XAUUSD") -> dict[str, Any]:
        balance = initial_balance
        equity_curve: list[float] = [balance]
        trades: list[BacktestTrade] = []
        self.risk_manager.update_equity_state(balance, balance)

        # Performance Turbo: Pre-calculate all indicators once
        self.logger.info("Preparing data indicators for backtest speedup...")
        prepared_data = self.strategy.prepare_data(frame)
        
        # Determine symbol config
        symbol_cfg = self.config["symbols"].get(symbol)
        if not symbol_cfg:
            symbol_cfg = next(iter(self.config["symbols"].values()))
        tick_size = float(symbol_cfg["point"])
        tick_value = float(symbol_cfg["contract_size"]) * tick_size
        risk_pct = float(self.config["risk"]["risk_per_trade_pct"])
        fee_per_lot = float(self.config["backtest"]["fee_per_lot"])
        
        # INFRA-1 & INFRA-2: Spread and slippage config
        avg_spread = float(self.config["backtest"].get("avg_spread_points", 0))
        max_slippage = float(self.config["backtest"].get("max_slippage_points", 0))
        
        # INFRA-3: Multi-bar holding config
        multi_bar = bool(self.config["backtest"].get("multi_bar_hold", False))
        max_hold_bars = int(self.config["backtest"].get("max_hold_bars", 48))

        self.logger.info("Starting fast backtest loop...")
        self.logger.info("  Spread: %.1f pts | Slippage: 0-%.1f pts | Multi-bar: %s (max %d)",
                         avg_spread, max_slippage, multi_bar, max_hold_bars)
        warmup = 1201 
        
        rows = [row for _, row in prepared_data.iloc[warmup:].iterrows()]
        
        i = 0
        while i < len(rows) - 1:
            current_row = rows[i]
            
            signals = self.strategy.generate_signals(prepared_data.iloc[warmup + i - 1 : warmup + i + 1], {})
            if not signals:
                equity_curve.append(balance)
                i += 1
                continue

            signal = max(signals, key=lambda item: item.confidence)
            
            risk_dist = abs(signal.entry - signal.sl)
            lot = self.risk_manager.calculate_lot(
                symbol=symbol,
                equity=balance,
                risk_pct=risk_pct,
                sl_distance_price=risk_dist,
                tick_size=tick_size,
                tick_value=tick_value,
                confidence_multiplier=signal.confidence,
            )

            # INFRA-1: Apply spread to entry price
            entry_price = self._apply_spread(signal.action, signal.entry, avg_spread, tick_size)
            spread_cost = avg_spread * tick_size * tick_value * lot  # Total spread cost

            # INFRA-2: Apply slippage to entry price
            if max_slippage > 0:
                slippage_amount = random.uniform(0, max_slippage) * tick_size
                if signal.action == "BUY":
                    entry_price += slippage_amount  # Worse fill for buy
                else:
                    entry_price -= slippage_amount  # Worse fill for sell

            # Adjust SL/TP relative to actual entry
            sl_adjusted = signal.sl
            tp_adjusted = signal.tp

            if multi_bar and i + 1 < len(rows):
                # INFRA-3: Multi-bar holding
                exit_price, pnl, bars_held = self._simulate_multi_bar_exit(
                    signal_action=signal.action,
                    entry_price=entry_price,
                    sl_price=sl_adjusted,
                    tp_price=tp_adjusted,
                    risk_dist=risk_dist,
                    tick_size=tick_size,
                    tick_value=tick_value,
                    lot=lot,
                    fee_per_lot=fee_per_lot,
                    spread_cost=spread_cost,
                    rows=rows,
                    start_idx=i + 1,
                    max_hold_bars=min(max_hold_bars, len(rows) - i - 1),
                )

                balance += pnl
                self.risk_manager.update_trade_outcome(pnl)
                self.risk_manager.update_equity_state(balance, balance)
                
                # Fill equity curve for all bars during hold
                for _ in range(bars_held):
                    equity_curve.append(balance)
                
                trades.append(
                    BacktestTrade(
                        time=rows[min(i + bars_held, len(rows) - 1)]["time"],
                        strategy=self.strategy.name,
                        action=signal.action,
                        entry=entry_price,
                        exit=exit_price,
                        pnl=pnl,
                        balance=balance,
                        hold_bars=bars_held,
                    )
                )
                
                print(f"\r{current_row['time'].strftime('%Y-%m')}| BAL: {balance:>12.2f} | Trades: {len(trades)}", end="")
                
                # Skip ahead past the bars the position was held
                i += bars_held
            else:
                # Single-bar exit (fallback)
                next_row = rows[i + 1]
                exit_price, pnl = self._simulate_single_bar_exit(
                    signal_action=signal.action,
                    entry_price=entry_price,
                    sl_price=sl_adjusted,
                    tp_price=tp_adjusted,
                    risk_dist=risk_dist,
                    tick_size=tick_size,
                    tick_value=tick_value,
                    lot=lot,
                    fee_per_lot=fee_per_lot,
                    spread_cost=spread_cost,
                    next_row=next_row,
                )

                balance += pnl
                self.risk_manager.update_trade_outcome(pnl)
                self.risk_manager.update_equity_state(balance, balance)
                equity_curve.append(balance)
                
                trades.append(
                    BacktestTrade(
                        time=next_row["time"],
                        strategy=self.strategy.name,
                        action=signal.action,
                        entry=entry_price,
                        exit=exit_price,
                        pnl=pnl,
                        balance=balance,
                    )
                )
                
                print(f"\r{current_row['time'].strftime('%Y-%m')}| BAL: {balance:>12.2f} | Trades: {len(trades)}", end="")
                i += 1

        print("\n") 
        equity_series = pd.Series(equity_curve, dtype=float)
        returns = equity_series.pct_change().dropna()
        sharpe = 0.0 if returns.std() == 0 else float((returns.mean() / returns.std()) * sqrt(252))
        drawdown = (equity_series / equity_series.cummax()) - 1

        avg_hold = sum(t.hold_bars for t in trades) / len(trades) if trades else 0

        return {
            "trades": trades,
            "trade_records": [
                {
                    "time": trade.time.isoformat(),
                    "strategy": trade.strategy,
                    "action": trade.action,
                    "entry": trade.entry,
                    "exit": trade.exit,
                    "pnl": trade.pnl,
                    "balance": trade.balance,
                    "hold_bars": trade.hold_bars,
                }
                for trade in trades
            ],
            "net_profit": balance - initial_balance,
            "ending_balance": balance,
            "max_drawdown_pct": abs(float(drawdown.min()) * 100) if not drawdown.empty else 0.0,
            "sharpe": sharpe,
            "win_rate": (
                sum(1 for trade in trades if trade.pnl > 0) / len(trades) * 100 if trades else 0.0
            ),
            "total_trades": len(trades),
            "avg_hold_bars": round(avg_hold, 1),
        }
