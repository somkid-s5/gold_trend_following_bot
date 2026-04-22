# 🏆 Gold Trend Following Bot - Institutional Grade

An advanced, high-performance algorithmic trading bot for Gold (XAUUSD), built with Python and MetaTrader 5. Engineered for **Super Aggressive** capital growth while maintaining a robust **Adaptive Resilience** system.

![Project Status](https://img.shields.io/badge/Status-Production--Ready-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

## 🚀 Key Features

### ⚡ Turbo Performance
*   **Vectorized Indicators**: Pre-calculates 10 years of data in seconds using Pandas.
*   **Fast Backtest Loop**: Execute 54,000+ bars (H1, 10 years) in under 15 seconds.
*   **Visual Terminal Mode**: Real-time ASCII dashboard showing Equity, PnL, and Drawdown during backtesting.

### 🛡️ Adaptive Resilience System
*   **Dynamic Risk Scaling**: Automatically scales risk per trade from **2.0% to 10.0%** based on strategy confidence (EMA Gap + RSI Momentum).
*   **D1 Trend Filter**: Higher-timeframe protection. Only takes trades that align with the daily (D1) trend.
*   **Sideway Shield**: Uses ADX and EMA Slope analysis to detect flat markets and reduce risk by up to 80% during choppy periods.
*   **Anti-Martingale Protection**: Automatically slashes lot sizes during consecutive losing streaks to protect core capital.

### 📊 Professional Monitoring
*   **Live Dashboard**: Professional poll-cycle logging showing Balance, Equity, Daily Drawdown, and Strategy Status.
*   **Telegram Integration**: Real-time alerts for trades, risk breaches, and daily performance summaries.
*   **Circuit Breaker**: Global drawdown protection that pauses the bot if losses exceed 15% to prevent catastrophic failure.

## 🛠️ Installation & Setup

### 1. Requirements
*   Python 3.10+
*   MetaTrader 5 (Exness or IC Markets recommended)
*   Dependencies: `pip install -r requirements.txt`

### 2. Configuration (`.env`)
Create a `.env` file in the root directory:
```env
MT5_LOGIN=433209659
MT5_PASSWORD="your_password"
MT5_SERVER="Exness-MT5Trial7"
MT5_PATH="C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"
```

### 3. Usage

#### **Run Live Trading**
```bash
python main.py --mode live --symbol XAUUSDm
```

#### **Run Fast Backtest (10 Years)**
```bash
python scripts/run_mt5_backtests.py --days 3650 --symbol XAUUSDm
```

#### **Analyze Trade History**
```bash
python scripts/analyze_trade_history.py
```

## 📈 Performance Summary (Backtest 2016-2026)
*   **Net Profit**: +$25,666.16 (On $10,000 initial)
*   **Win Rate**: 51.55%
*   **Max Drawdown**: 67.20% (Aggressive mode)
*   **Sharpe Ratio**: 0.13

## 📁 Project Structure
*   `src/core`: Main trading engine and poll cycles.
*   `src/strategies`: Trend following logic with ADX and HTF filters.
*   `src/risk`: Adaptive lot calculation and equity protection.
*   `src/broker`: MetaTrader 5 bridge and order execution.
*   `scripts`: High-performance backtesting and analysis tools.

---
**Disclaimer**: This bot is configured for high-risk trading (up to 10% per trade). Use with caution and always validate on a demo account before going live.
