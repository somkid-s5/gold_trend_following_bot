# Gold Trading Bot

Python trading bot structure for XAUUSD on MetaTrader 5 with three strategy modules:

- `trend_following`: EMA50/200 + RSI14 cross + ATR14 stop.
- `scalping_smc`: M5 London-NY overlap breakout using Bollinger squeeze, MACD momentum, volume burst, and a simple fair-value-gap proxy.
- `linear_grid`: bounded H4 supply-demand grid with ATR-based spacing and global TP.

The project now also includes:

- automatic MT5 reconnect handling
- breakeven and trailing-stop management for live positions
- pluggable news calendar input from manual config, local JSON, or JSON URL
- sample CSV data and test coverage for strategies, risk, and backtest flow

## Project structure

```text
gold_trading_bot/
├── config/
│   └── config.yaml
├── src/
│   ├── broker/
│   │   └── mt5_connector.py
│   ├── data/
│   │   └── data_handler.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── trend_following.py
│   │   ├── scalping_smc.py
│   │   └── linear_grid.py
│   ├── risk/
│   │   └── risk_manager.py
│   ├── core/
│   │   └── trading_engine.py
│   └── utils/
│       ├── logger.py
│       └── backtester.py
├── main.py
├── requirements.txt
└── README.md
```

## Install

```bash
pip install -r requirements.txt
```

## Configure

Update `config/config.yaml` before live usage:

- `mt5.login`, `mt5.password`, `mt5.server`
- `risk.allow_live_trading=true` only after demo testing
- `news_filter.provider` set to `manual`, `json_file`, or `json_url`
- `news_filter.high_impact_events` or JSON feed entries with UTC timestamps
- `backtest.csv_path` to your exported historical dataset

Example JSON file for news events:

```json
{
  "events": [
    {"time": "2026-03-25T12:30:00+00:00"},
    {"time": "2026-03-27T12:30:00+00:00"}
  ]
}
```

## Run

Live:

```bash
python main.py --mode=live --symbol=XAUUSD --strategy=trend_following
```

Backtest:

```bash
python main.py --mode=backtest --symbol=XAUUSD --strategy=trend_following --csv=data/xauusd_h1.csv
```

Run tests:

```bash
python -m unittest discover -s tests
```

Generate a quick report from the latest bot log:

```bash
python main.py --mode=report
```

Generate a report from an exported backtest trade CSV:

```bash
python main.py --mode=report --report-source=reports/trend_following_backtest_trades.csv
```

Run a 12-month in-sample / out-of-sample check for the trend strategy:

```bash
python scripts/run_trend_oos_analysis.py --symbol XAUUSD --days 365 --split-ratio 0.7
```

## Backtest data

The backtester consumes a CSV with:

```text
time,open,high,low,close,volume
2026-01-01T00:00:00Z,2620.1,2625.7,2618.3,2623.5,1450
```

You can export the historical candles from MT5 and save them locally for offline testing.

A synthetic starter dataset is included at `data/xauusd_m5.csv` so the backtester can run immediately.

## Safety notes

- Hard stop loss is mandatory for every order.
- Grid logic is bounded by `max_positions` and daily drawdown limits.
- News filter supports manual config, local JSON, or JSON URL feeds.
- Add broker-specific checks for `ORDER_FILLING_*`, slippage, and symbol suffixes such as `XAUUSDm`.
- Backtests export trade-by-trade CSV reports into `reports/` automatically.
