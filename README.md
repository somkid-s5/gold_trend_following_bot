# Gold Trading Bot

Python trading bot structure for XAUUSD on MetaTrader 5.

Current operational default:

- `trend_following`: enabled and tuned from 12-month backtest plus out-of-sample validation

Research-only modules:

- `scalping_smc`: disabled by default
- `linear_grid`: disabled by default

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

`main.py` now loads `.env` automatically, refreshes guard status from MT5 deal history, writes a runtime heartbeat, and will stop opening new entries if the operational guard flips to `PAUSE`.

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

Run trend parameter tuning:

```bash
python scripts/run_trend_grid_search.py --symbol XAUUSD --days 365 --split-ratio 0.7 --fast-emas 34,50 --slow-emas 150,200 --buy-levels 35,40 --sell-levels 60,65 --atr-multipliers 1.2,1.5 --rr-values 1.5,2.0 --top 8
```

Create a forward-test report from exported trades:

```bash
python scripts/run_forward_test_report.py --trades-csv=reports/trend_following_365d_trades.csv --strategy=trend_following
```

Evaluate operational stop conditions from recent trades:

```bash
python scripts/run_operational_guard_check.py --trades-csv=reports/trend_following_365d_trades.csv
```

Unattended run flow:

```bash
python main.py --mode=live --symbol=XAUUSD --strategy=trend_following
```

Monitor these files while it runs:

- `reports/runtime_status.json`
- `reports/guard_status.json`
- `logs/gold_trading_bot.log`

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
- Use [FORWARD_TEST_CHECKLIST.md](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/FORWARD_TEST_CHECKLIST.md) for Demo validation before any live rollout.
- If `reports/guard_status.json` switches to `PAUSE`, the live engine will stop opening new entries.
