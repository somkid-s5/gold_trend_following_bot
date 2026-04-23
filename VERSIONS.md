# 📜 Gold Trend Following - Version History

## 🟢 main [Legacy Stable]
- **Strategy:** Pure EMA 34/150 Crossover + RSI 35/65
- **Risk Management:** Fixed 2.0% per trade, Fixed TP/SL (RR 3.5)
- **Performance:** ~$20,786 profit (10 years)
- **Characteristics:** High frequency (1,400 trades), captures many small moves, but prone to whipsaws.

## 🔵 feat/institutional-grade-v2 [Smart Hunter]
- **Strategy:** EMA 34/150 + **ADX Filter (>16)**
- **Risk Management:** Increased Risk 3.5%, **Trailing Stop (Lock RR 1.0 at RR 2.0)**, RR 5.0
- **Performance:** **$26,762 profit (10 years)**
- **Characteristics:** High efficiency (749 trades), filters out 45% of "fake" trades, locks profit mid-trend.

## 🔴 feat/institutional-grade-v3-hyper [The $50k Quest] - *Current Development*
- **Planned Upgrades:** Winning Streak Compounding, Volatility-Adjusted Sizing, and Time-Based Stagnation Exit.
- **Goal:** Reach $50,000+ profit without breaking the 65% Drawdown barrier.
