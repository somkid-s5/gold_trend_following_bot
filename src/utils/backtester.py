from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

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


class Backtester:
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
                }
                for trade in trades
            ]
        )
        frame.to_csv(path, index=False)
        return path

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

        self.logger.info("Starting fast backtest loop...")
        warmup = 1201 
        
        rows = [row for _, row in prepared_data.iloc[warmup:].iterrows()]
        
        for i in range(len(rows) - 1):
            current_row = rows[i]
            next_row = rows[i+1]
            
            signals = self.strategy.generate_signals(prepared_data.iloc[warmup + i - 1 : warmup + i + 1], {})
            if not signals:
                equity_curve.append(balance)
                continue

            signal = max(signals, key=lambda item: item.confidence)
            
            lot = self.risk_manager.calculate_lot(
                equity=balance,
                risk_pct=risk_pct,
                sl_distance_price=abs(signal.entry - signal.sl),
                tick_size=tick_size,
                tick_value=tick_value,
                confidence_multiplier=signal.confidence,
            )

            # --- STABLE TRAILING STOP SIMULATION (Stage 3) ---
            entry_price = signal.entry
            sl_price = signal.sl
            tp_price = signal.tp
            
            high = float(next_row["high"])
            low = float(next_row["low"])
            close = float(next_row["close"])
            
            risk_dist = abs(entry_price - sl_price)
            trail_trigger = entry_price + (risk_dist * 2.0) if signal.action == "BUY" else entry_price - (risk_dist * 2.0)
            
            exit_price = close
            
            if signal.action == "BUY":
                if low <= sl_price:
                    exit_price = sl_price
                elif high >= trail_trigger:
                    # Trailing: Move SL to RR 1.0 to lock profit
                    sl_price = entry_price + risk_dist
                    if high >= tp_price: exit_price = tp_price
                    elif low <= sl_price: exit_price = sl_price
                elif high >= tp_price: exit_price = tp_price
            else: # SELL
                if high >= sl_price:
                    exit_price = sl_price
                elif low <= trail_trigger:
                    # Trailing: Move SL to RR 1.0 to lock profit
                    sl_price = entry_price - risk_dist
                    if low <= tp_price: exit_price = tp_price
                    elif high >= sl_price: exit_price = sl_price
                elif low <= tp_price: exit_price = tp_price

            pnl = (exit_price - entry_price) / tick_size * tick_value * lot if signal.action == "BUY" else (entry_price - exit_price) / tick_size * tick_value * lot
            pnl -= fee_per_lot * lot
            balance += pnl
            self.risk_manager.update_trade_outcome(pnl)
            self.risk_manager.update_equity_state(balance, balance)
            equity_curve.append(balance)
            
            print(f"\r{current_row['time'].strftime('%Y-%m')}| BAL: {balance:>10.2f}", end="")

            trades.append(
                BacktestTrade(
                    time=next_row["time"],
                    strategy=self.strategy.name,
                    action=signal.action,
                    entry=signal.entry,
                    exit=exit_price,
                    pnl=pnl,
                    balance=balance,
                )
            )

        print("\n") 
        equity_series = pd.Series(equity_curve, dtype=float)
        returns = equity_series.pct_change().dropna()
        sharpe = 0.0 if returns.std() == 0 else float((returns.mean() / returns.std()) * sqrt(252))
        drawdown = (equity_series / equity_series.cummax()) - 1

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
        }
