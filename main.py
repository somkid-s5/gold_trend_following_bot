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
from src.utils.backtester import Backtester
from src.utils.logger import setup_logger
from src.utils.reporting import PerformanceReporter
from src.utils.telegram_notifier import TelegramNotifier


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        if line.startswith("#") and line.find("=") > line.find("#"):
             if not any(char.isalnum() for char in line[:line.find("=")]):
                 continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("#"):
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    mt5_cfg = config.setdefault("mt5", {})
    if os.getenv("MT5_LOGIN"):
        mt5_cfg["login"] = int(os.getenv("MT5_LOGIN", "0"))
    if os.getenv("MT5_PASSWORD"):
        mt5_cfg["password"] = os.getenv("MT5_PASSWORD")
    if os.getenv("MT5_SERVER"):
        mt5_cfg["server"] = os.getenv("MT5_SERVER")
    if os.getenv("MT5_PATH"):
        mt5_cfg["path"] = os.getenv("MT5_PATH")
    return config


def build_strategy(config: dict[str, Any]) -> TrendFollowing:
    return TrendFollowing(config["strategies"]["trend_following"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gold trend-following bot for MT5")
    parser.add_argument("--mode", choices=["live", "backtest", "report"], default="backtest")
    parser.add_argument("--symbol", default=None) # Default to None to use config value
    parser.add_argument("--strategy", choices=["trend_following"], default="trend_following")
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    parser.add_argument("--csv", default=None, help="CSV path for backtests")
    parser.add_argument("--report-source", default=None, help="CSV or log file path for report mode")
    return parser.parse_args()


def run_live(config: dict[str, Any], symbol: str) -> None:
    load_dotenv(ROOT / ".env")
    config = apply_env_overrides(config)
    
    # CRITICAL: If no symbol passed via CLI, use the one from config.yaml
    actual_symbol = symbol or config.get("trading", {}).get("symbol", "XAUUSDm")

    logger = setup_logger()
    connector = MT5Connector(config["mt5"])
    data_handler = DataHandler(connector)
    
    # Try to find symbol info in config, case-insensitive
    symbol_info = config["symbols"].get(actual_symbol)
    if not symbol_info:
        # Fallback search
        for k, v in config["symbols"].items():
            if k.lower() == actual_symbol.lower():
                symbol_info = v
                actual_symbol = k # Use the correct key from config
                break
    
    if not symbol_info:
        raise KeyError(f"Symbol {actual_symbol} not defined in config symbols section")

    risk_manager = RiskManager(config["risk"], symbol_info)
    notifier = TelegramNotifier(config.get("notifications", {}).get("telegram", {}), logger)
    engine = TradingEngine(
        connector=connector,
        data_handler=data_handler,
        risk_manager=risk_manager,
        strategies={"trend_following": build_strategy(config)},
        config=config,
        logger=logger,
        mode="live",
        notifier=notifier,
    )

    try:
        while True:
            try:
                if not connector.initialized:
                    connector.connect_mt5()
                    logger.info("Connected to MT5")
                
                results = engine.run(symbol=actual_symbol, strategy_name="trend_following")
                for result in results:
                    logger.info("%s | %s | %s", result.strategy, result.status, result.details)
                
                poll_delay = int(config.get("trading", {}).get("poll_seconds", 60))
                time.sleep(poll_delay)

            except Exception as exc:
                logger.exception("Live loop error: %s", exc)
                reconnect_delay = int(config.get("trading", {}).get("reconnect_seconds", 15))
                connector.disconnect()
                time.sleep(reconnect_delay)
    finally:
        connector.disconnect()


def run_backtest(config: dict[str, Any], symbol: str, csv_path: str | None) -> None:
    actual_symbol = symbol or config.get("trading", {}).get("symbol", "XAUUSDm")
    logger = setup_logger()
    data_handler = DataHandler()
    dataset = csv_path or config["backtest"].get("csv_path")
    dataset_path = ROOT / dataset if not Path(dataset).is_absolute() else Path(dataset)
    frame = data_handler.load_csv(dataset_path)
    strategy = build_strategy(config)
    risk_manager = RiskManager(config["risk"], config["symbols"][actual_symbol])
    backtester = Backtester(strategy, risk_manager, config, logger)
    results = backtester.run(frame, float(config["backtest"]["initial_balance"]), symbol=actual_symbol)
    
    logger.info("Backtest finished for trend_following. Profit: %.2f", results["net_profit"])


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    config = apply_env_overrides(load_config(Path(args.config)))

    if args.mode == "live":
        run_live(config, args.symbol)
    else:
        run_backtest(config, args.symbol, args.csv)


if __name__ == "__main__":
    main()
