# TITAN Singularity Architecture

## Overview
TITAN Singularity (God Mode) is the ultimate multi-symbol algorithmic trading system designed for MetaTrader 5. It is built to maximize profit velocity through exponential pyramiding and real-time compounding, backed by a decoupled architecture with a FastAPI backend and a React/Vite dashboard.

## System Components

### 1. Trading Engine (`src/core/trading_engine.py`)
The "brain" of the system.
- **Trend Pyramiding**: Adds up to 10 positions dynamically every 2.0 ATR when the price aligns with the EMA 200 macro trend.
- **Zero Friction**: Removed conservative volume filters to capture every institutional breakout.
- **Ultra-Fast Breakeven**: Moves SL to entry + 1 point at just 0.5 RR.

### 2. Strategy Layer (`src/strategies/`)
- **TrendFollowing (Singularity)**: An unchained institutional strategy that detects Tokyo Range breakouts and leverages EMA 21 / EMA 200.

### 3. Broker Connector (`src/broker/mt5_connector.py`)
Handles direct, ultra-low latency execution with MT5.

### 4. Risk Manager (`src/risk/risk_manager.py`)
A highly aggressive but dynamically intelligent capital protector.
- **Singularity Scaling**: Computes lot sizes dynamically using 100% of real-time equity. No delays, no step deltas.
- **Dynamic Drawdown Protection**: Reduces risk from 15% to 5% instantly after a single loss to prevent capital death spirals.

### 5. API & Dashboard (`api/` and `frontend/`)
Provides a user-friendly interface to control and monitor the Singularity Engine.
- **BotManager**: Handles starting/stopping the engine as a separate process.
- **Unified Backtest**: Runs simulations and generates JSON/CSV reports.

## Data Flow
1. **Fetch**: Engine requests data via DataHandler → MT5Connector.
2. **Analyze**: Strategy generates Signals based on historical bars.
3. **Validate**: RiskManager verifies if the signal meets safety criteria, adjusting risk dynamically.
4. **Execute**: MT5Connector sends orders to the broker (capable of high-frequency pyramiding).
5. **Monitor**: API polls the logs and account status to update the Dashboard.