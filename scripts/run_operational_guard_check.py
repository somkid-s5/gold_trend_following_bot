from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import load_config
from src.core.operational_guards import OperationalGuardEvaluator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate operational stop conditions from a trades CSV")
    parser.add_argument("--trades-csv", required=True)
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    evaluator = OperationalGuardEvaluator(config.get("operational_guards", {}))
    status = evaluator.evaluate_trade_csv(args.trades_csv)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status.status,
        "reasons": status.reasons,
        "metrics": status.metrics,
        "source_csv": str(Path(args.trades_csv).resolve()),
    }

    output_path = ROOT / config["operational_guards"]["guard_report_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"\nGuard report written to: {output_path}")


if __name__ == "__main__":
    main()
