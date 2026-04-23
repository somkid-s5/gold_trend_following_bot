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

## 🔴 feat/institutional-grade-v3-hyper [The Final Berserker]
- **Strategy:** EMA 34/150 + **D1 Trend Filter** + **Sniper Session Filter (10-22 UTC)** + **Pullback Multi-Entry**
- **Risk Management:** Hyper Win-Boost (up to 10.0x), Trailing Stop (RR 1.0 @ RR 2.0), Dynamic RR (5.0-7.0)
- **Performance:** **$25,081 profit (10 years)**
- **Max Drawdown:** **39.76%** (Very Stable)
- **Characteristics:** The ultimate balance of high accuracy (53.5%) and aggressive compounding. This is the master version.
