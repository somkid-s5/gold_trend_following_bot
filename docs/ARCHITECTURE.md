# TITAN Berserker Architecture

## Overview
TITAN Berserker is a multi-symbol algorithmic trading system designed for MetaTrader 5. It uses a modern decoupled architecture with a FastAPI backend and a React/Vite frontend dashboard.

## System Components

### 1. Trading Engine (`src/core/trading_engine.py`)
The "brain" of the system. It handles:
- Portfolio coordination across multiple symbols.
- Signal generation and validation.
- Risk management checks (spread, drawdown, news filter).
- Automated position management (Trailing Stop, Breakeven).

### 2. Strategy Layer (`src/strategies/`)
Contains the trading logic.
- **TrendFollowing**: An institutional-grade strategy based on Tokyo Range breakouts and EMA trend bias.

### 3. Broker Connector (`src/broker/mt5_connector.py`)
Handles all direct communication with MetaTrader 5.
- Order execution and position modification.
- Historical data fetching.
- Real-time price monitoring.

### 4. Risk Manager (`src/risk/risk_manager.py`)
A standalone layer for capital protection.
- Dynamic lot sizing based on scaling delta.
- Hard risk caps and circuit breakers.

### 5. API & Dashboard (`api/` and `frontend/`)
Provides a user-friendly interface to control and monitor the bot.
- **BotManager**: Handles starting/stopping the engine as a separate process.
- **Unified Backtest**: Runs simulations and generates JSON/CSV reports.

## Data Flow
1. **Fetch**: Engine requests data via DataHandler → MT5Connector.
2. **Analyze**: Strategy generates Signals based on historical bars.
3. **Validate**: RiskManager verifies if the signal meets safety criteria.
4. **Execute**: MT5Connector sends orders to the broker.
5. **Monitor**: API polls the logs and account status to update the Dashboard.
