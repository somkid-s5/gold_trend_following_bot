import json
import os
from pathlib import Path
from datetime import datetime

class InvestmentTracker:
    def __init__(self, data_path: str = "data/investment_state.json"):
        self.path = Path(data_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({"total_invested": 0.0, "last_deposit_at": None, "history": []})

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def add_deposit(self, amount_usd: float, note: str = "DCA"):
        data = self._load()
        data["total_invested"] += amount_usd
        data["last_deposit_at"] = datetime.now().isoformat()
        data["history"].append({
            "date": data["last_deposit_at"],
            "amount": amount_usd,
            "note": note
        })
        self._save(data)
        return data["total_invested"]

    def get_total_invested(self):
        return self._load()["total_invested"]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--amount", type=float, required=True, help="Amount in USD to add")
    parser.add_argument("--note", default="DCA", help="Optional note")
    args = parser.parse_args()
    
    tracker = InvestmentTracker()
    total = tracker.add_deposit(args.amount, args.note)
    print(f"DEPOSIT RECORDED: +${args.amount:,.2f}")
    print(f"TOTAL INVESTED CAPITAL: ${total:,.2f}")
