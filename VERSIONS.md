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

## 💀 feat/institutional-grade-v4-100k [Failed Titan Experiments]
- **Attempts:** Titan Mode (10% Base Risk), Sniper Assassin (8.0 RR), Quantum Moonshot (Mean Reversion).
- **Results:** Port crashed or severely depleted in all scenarios. 
- **Conclusion:** Market volatility on H1 is too high for >5% base risk. Hyper-aggression leads to geometric ruin.
- **The True Path to $100k:** Scale this bot across 4 uncorrelated symbols (XAUUSD, GBPUSD, EURUSD, BTCUSD) using the stable v3-hyper logic. 4 x $25k = $100k with low risk.
