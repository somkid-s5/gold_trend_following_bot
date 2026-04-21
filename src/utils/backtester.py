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

        warmup = 220
        for index in range(warmup, len(frame) - 1):
            window = frame.iloc[: index + 1].copy()
            signals = self.strategy.generate_signals(window, {})
            if not signals:
                equity_curve.append(balance)
                continue

            signal = max(signals, key=lambda item: item.confidence)
            next_bar = frame.iloc[index + 1]
            
            # Use the provided symbol to look up configuration
            symbol_cfg = self.config["symbols"].get(symbol)
            if not symbol_cfg:
                # Fallback to the first symbol if the specific one is missing
                symbol_cfg = next(iter(self.config["symbols"].values()))
                
            tick_size = float(symbol_cfg["point"])
            tick_value = float(symbol_cfg["contract_size"]) * tick_size
            lot = self.risk_manager.calculate_lot(
                equity=balance,
                risk_pct=float(self.config["risk"]["risk_per_trade_pct"]),
                sl_distance_price=abs(signal.entry - signal.sl),
                tick_size=tick_size,
                tick_value=tick_value,
                confidence_multiplier=signal.confidence,
            )

            exit_price = float(next_bar["close"])
            hit_sl = signal.action == "BUY" and float(next_bar["low"]) <= signal.sl
            hit_tp = signal.action == "BUY" and float(next_bar["high"]) >= signal.tp
            sell_sl = signal.action == "SELL" and float(next_bar["high"]) >= signal.sl
            sell_tp = signal.action == "SELL" and float(next_bar["low"]) <= signal.tp

            if signal.action == "BUY":
                if hit_sl:
                    exit_price = signal.sl
                elif hit_tp:
                    exit_price = signal.tp
                pnl = (exit_price - signal.entry) / tick_size * tick_value * lot
            else:
                if sell_sl:
                    exit_price = signal.sl
                elif sell_tp:
                    exit_price = signal.tp
                pnl = (signal.entry - exit_price) / tick_size * tick_value * lot

            pnl -= float(self.config["backtest"]["fee_per_lot"]) * lot
            balance += pnl
            self.risk_manager.update_equity_state(balance, balance)
            equity_curve.append(balance)
            trades.append(
                BacktestTrade(
                    time=next_bar["time"],
                    strategy=self.strategy.name,
                    action=signal.action,
                    entry=signal.entry,
                    exit=exit_price,
                    pnl=pnl,
                    balance=balance,
                )
            )

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
