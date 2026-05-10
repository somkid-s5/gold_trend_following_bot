from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.broker.mt5_connector import MT5Connector
from src.core.trading_engine import TradingEngine
from src.data.data_handler import DataHandler
from src.risk.risk_manager import RiskManager
from src.strategies.trend_following import TrendFollowing
from src.utils.logger import setup_logger
from src.utils.telegram_notifier import TelegramNotifier


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists(): return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line: continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("#"): continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    mt5_cfg = config.setdefault("mt5", {})
    for k in ["MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER", "MT5_PATH"]:
        if os.getenv(k):
            val = os.getenv(k)
            mt5_cfg[k.replace("MT5_", "").lower()] = int(val) if "LOGIN" in k else val
            
    # FIXED: 9
    if mt5_cfg.get("login", 0) == 0:
        raise EnvironmentError("MT5_LOGIN is missing or 0. Please set it in .env")
        
    return config


def build_strategy(config: dict[str, Any]) -> TrendFollowing:
    return TrendFollowing(config["strategies"]["trend_following"])


def run_live(config: dict[str, Any]) -> None:
    load_dotenv(ROOT / ".env")
    config = apply_env_overrides(config)
    logger = setup_logger()
    
    # --- MULTI-SYMBOL INITIALIZATION ---
    connector = MT5Connector(config["mt5"])
    data_handler = DataHandler(connector)
    # Pass the entire symbols dictionary to RiskManager
    risk_manager = RiskManager(config["risk"], config["symbols"])
    notifier = TelegramNotifier(config.get("notifications", {}).get("telegram", {}), logger)
    
    engine = TradingEngine(
        connector=connector,
        data_handler=data_handler,
        risk_manager=risk_manager,
        strategies={"trend_following": TrendFollowing(config["strategies"]["trend_following"])},
        config=config,
        logger=logger,
        mode="live",
        notifier=notifier,
    )

    logger.info("⚡ TITAN PORTFOLIO ENGINE ACTIVE")
    logger.info("🌍 SCANNING: %s", ", ".join(config["symbols"].keys()))

    try:
        while True:
            try:
                if not connector.initialized:
                    connector.connect_mt5()
                    logger.info("CONNECTED TO MT5")
                
                # Check for signals across all symbols
                results = engine.run_portfolio()
                for res in results:
                    logger.info("ENGINE | %s: %s - %s", res.strategy.upper(), res.status.upper(), res.details)
                
                time.sleep(int(config.get("trading", {}).get("poll_seconds", 60)))

            except Exception as exc:
                logger.exception("LIVE LOOP ERROR: %s", exc)
                time.sleep(15)
    finally:
        connector.disconnect()


def main() -> None:
    args = argparse.ArgumentParser(description="TITAN Multi-Symbol Bot")
    args.add_argument("--mode", choices=["live", "backtest"], default="live")
    args.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    parsed = args.parse_args()
    
    config = load_config(Path(parsed.config))
    if parsed.mode == "live":
        run_live(config)
    else:
        print("Use scripts/run_backtest.py for testing.")

if __name__ == "__main__":
    main()
