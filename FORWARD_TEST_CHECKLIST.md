# Forward Test Checklist

Use this checklist before enabling live trading.

## Setup

- Confirm only `trend_following` is enabled in [config/config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml).
- Keep `risk.allow_live_trading=false` while testing on Demo.
- Verify MT5 account, symbol name, spread, and trading session are correct.
- Confirm high-impact news times are updated in the news filter.

## Daily Review

- Check that the bot stayed connected and no repeated reconnect loop appeared in the log.
- Review new trades and confirm every trade has SL and TP set.
- Verify no trade was opened during blocked news windows.
- Note total trades, daily PnL, and any slippage or spread anomalies.

## Weekly Review

- Compare forward-test win rate and average trade to the 12-month backtest baseline.
- Check if max consecutive losses remain within expected range.
- Confirm weekly trade count is close to the configured target.
- Pause the bot if behavior diverges materially from the backtest.

## Promotion Gate

- At least 14 forward-test days completed.
- No critical execution bugs or repeated MT5 disconnect failures.
- Risk controls triggered correctly during abnormal conditions.
- Forward-test results remain positive or acceptably flat with controlled drawdown.
