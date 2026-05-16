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
            
    if mt5_cfg.get("login", 0) == 0:
        raise EnvironmentError("MT5_LOGIN is missing or 0. Please set it in .env")
        
    return config


def build_strategy(config: dict[str, Any]) -> TrendFollowing:
    return TrendFollowing(config["strategies"]["trend_following"])


def run_live(config: dict[str, Any], logger: Any) -> None:
    load_dotenv(ROOT / ".env")
    config = apply_env_overrides(config)
    
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


def start_dashboard(logger: Any) -> Any:
    import subprocess
    import sys
    
    # Check if dashboard is already running (simple check)
    try:
        import requests
        resp = requests.get("http://127.0.0.1:8000/api/bot/status", timeout=1)
        if resp.status_code == 200:
            logger.info("Dashboard API is already running.")
            return None
    except:
        pass

    logger.info("🚀 Starting API Dashboard in background...")
    # Run uvicorn as a subprocess
    cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    
    # Use CREATE_NO_WINDOW on Windows to keep it hidden or just subprocess.DEVNULL
    process = subprocess.Popen(
        cmd, 
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    
    logger.info("✅ Dashboard available at: http://localhost:8000")
    return process


def write_pid():
    pid_file = ROOT / "logs" / "bot.pid"
    pid_file.parent.mkdir(exist_ok=True)
    pid_file.write_text(str(os.getpid()))

def remove_pid():
    pid_file = ROOT / "logs" / "bot.pid"
    if pid_file.exists():
        pid_file.unlink()


def main() -> None:
    args = argparse.ArgumentParser(description="TITAN Multi-Symbol Bot")
    args.add_argument("--mode", choices=["live", "backtest"], default="live")
    args.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args.add_argument("--no-dashboard", action="store_true", help="Do not start the API dashboard")
    parsed = args.parse_args()
    
    config = load_config(Path(parsed.config))
    logger = setup_logger()

    api_process = None
    if parsed.mode == "live" and not parsed.no_dashboard:
        api_process = start_dashboard(logger)

    try:
        if parsed.mode == "live":
            write_pid()
            run_live(config, logger)
        else:
            print("Use scripts/run_backtest.py for testing.")
    except KeyboardInterrupt:
        logger.info("Exiting...")
    finally:
        remove_pid()
        if api_process:
            logger.info("Stopping Dashboard...")
            if os.name == 'nt':
                import signal
                api_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                api_process.terminate()
            api_process.wait(timeout=5)

if __name__ == "__main__":
    main()
