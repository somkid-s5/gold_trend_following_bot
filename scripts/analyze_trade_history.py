from __future__ import annotations
import pandas as pd
from pathlib import Path
import json

def main():
    csv_path = Path("reports/trend_following_3650d_trades.csv")
    if not csv_path.exists():
        print("CSV file not found")
        return

    df = pd.read_csv(csv_path)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)

    # Calculate Monthly PnL
    monthly_pnl = df['pnl'].resample('ME').sum()
    yearly_pnl = df['pnl'].resample('YE').sum()

    # Create Yearly Summary Table
    print("\n=== YEARLY PERFORMANCE SUMMARY ===")
    print(f"{'Year':<10} | {'Profit/Loss ($)':<15} | {'Trades':<10}")
    print("-" * 45)
    for year, pnl in yearly_pnl.items():
        trades_count = df[df.index.year == year.year].shape[0]
        print(f"{year.year:<10} | {pnl:>15.2f} | {trades_count:<10}")

    # Identify Best and Worst Months
    best_month = monthly_pnl.idxmax()
    worst_month = monthly_pnl.idxmin()

    print(f"\nBEST MONTH: {best_month.strftime('%B %Y')} (+${monthly_pnl.max():.2f})")
    print(f"WORST MONTH: {worst_month.strftime('%B %Y')} (-${monthly_pnl.min():.2f})")

    # Generate a simple text-based bar chart for the last 2 years (Monthly)
    print("\n=== MONTHLY PERFORMANCE (Last 24 Months) ===")
    last_24 = monthly_pnl.tail(24)
    for month, pnl in last_24.items():
        bar_len = int(abs(pnl) / 200) # Scale bar
        bar = ("+" * bar_len) if pnl > 0 else ("-" * bar_len)
        print(f"{month.strftime('%b %Y'):<10} | {pnl:>10.2f} | {bar}")

if __name__ == "__main__":
    main()
