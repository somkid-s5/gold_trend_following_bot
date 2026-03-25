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
from src.strategies.linear_grid import LinearGrid
from src.strategies.scalping_smc import ScalpingSMC
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
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_strategies(config: dict[str, Any]) -> dict[str, Any]:
    strategy_map = {
        "trend_following": lambda: TrendFollowing(config["strategies"]["trend_following"]),
        "scalping_smc": lambda: ScalpingSMC(
            config["strategies"]["scalping_smc"],
            config["sessions"]["london_ny_overlap"],
        ),
        "linear_grid": lambda: LinearGrid(config["strategies"]["linear_grid"]),
    }
    enabled: dict[str, Any] = {}
    for name, factory in strategy_map.items():
        if config["strategies"][name].get("enabled", True):
            enabled[name] = factory()
    return enabled


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gold trading bot for MT5")
    parser.add_argument("--mode", choices=["live", "backtest", "report"], default="backtest")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--strategy", choices=["trend_following", "scalping_smc", "linear_grid"], default="trend_following")
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    parser.add_argument("--csv", default=None, help="CSV path for backtests")
    parser.add_argument("--report-source", default=None, help="CSV or log file path for report mode")
    return parser.parse_args()


def run_live(config: dict[str, Any], symbol: str, strategy_name: str | None) -> None:
    logger = setup_logger()
    connector = MT5Connector(config["mt5"])
    data_handler = DataHandler(connector)
    risk_manager = RiskManager(config["risk"], config["symbols"][symbol])
    notifier = TelegramNotifier(config.get("notifications", {}).get("telegram", {}), logger)
    engine = TradingEngine(
        connector=connector,
        data_handler=data_handler,
        risk_manager=risk_manager,
        strategies=build_strategies(config),
        config=config,
        logger=logger,
        mode="live",
        notifier=notifier,
    )
    startup_alert_sent = False

    try:
        while True:
            try:
                if not connector.initialized:
                    connector.connect_mt5()
                    logger.info("Connected to MT5")
                    if (
                        notifier.is_enabled()
                        and config.get("notifications", {}).get("telegram", {}).get("send_startup_alerts", True)
                        and not startup_alert_sent
                    ):
                        stamp = datetime.now(timezone.utc)
                        if notifier.should_send_event("startup", stamp):
                            notifier.send_message(
                                notifier.build_event_message("Startup", stamp, f"Connected to MT5 for {symbol}")
                            )
                            notifier.mark_event_sent("startup", stamp)
                        startup_alert_sent = True
                results = engine.run(symbol=symbol, strategy_name=strategy_name)
                for result in results:
                    logger.info("%s | %s | %s", result.strategy, result.status, result.details)
                time.sleep(int(config["trading"]["poll_seconds"]))
            except Exception as exc:
                logger.exception("Live loop error: %s", exc)
                if notifier.is_enabled() and config.get("notifications", {}).get("telegram", {}).get("send_error_alerts", True):
                    stamp = datetime.now(timezone.utc)
                    if notifier.should_send_event("error", stamp):
                        notifier.send_message(
                            notifier.build_event_message("Error", stamp, str(exc))
                        )
                        notifier.mark_event_sent("error", stamp)
                connector.disconnect()
                time.sleep(int(config["trading"].get("reconnect_seconds", 15)))
    finally:
        connector.disconnect()
        logger.info("Disconnected from MT5")
        if notifier.is_enabled() and config.get("notifications", {}).get("telegram", {}).get("send_shutdown_alerts", True):
            stamp = datetime.now(timezone.utc)
            if notifier.should_send_event("shutdown", stamp):
                notifier.send_message(
                    notifier.build_event_message("Shutdown", stamp, f"Disconnected from MT5 for {symbol}")
                )
                notifier.mark_event_sent("shutdown", stamp)


def run_backtest(config: dict[str, Any], symbol: str, strategy_name: str, csv_path: str | None) -> None:
    logger = setup_logger()
    data_handler = DataHandler()
    dataset = csv_path or config["backtest"]["csv_path"]
    dataset_path = ROOT / dataset if not Path(dataset).is_absolute() else Path(dataset)
    frame = data_handler.load_csv(dataset_path)
    strategy = build_strategies(config)[strategy_name]
    risk_manager = RiskManager(config["risk"], config["symbols"][symbol])
    backtester = Backtester(strategy, risk_manager, config, logger)
    results = backtester.run(frame, float(config["backtest"]["initial_balance"]))
    reports_dir = ROOT / "reports"
    trades_path = reports_dir / f"{strategy_name}_backtest_trades.csv"
    backtester.export_trades(results["trades"], trades_path)

    logger.info("Backtest finished for %s", strategy_name)
    logger.info(
        "Trades=%s NetProfit=%.2f Sharpe=%.2f MaxDD=%.2f%% WinRate=%.2f%%",
        results["total_trades"],
        results["net_profit"],
        results["sharpe"],
        results["max_drawdown_pct"],
        results["win_rate"],
    )
    logger.info("Trades exported to %s", trades_path)


def run_report(report_source: str | None) -> None:
    logger = setup_logger()
    reporter = PerformanceReporter()
    source = Path(report_source) if report_source else ROOT / "logs" / "gold_trading_bot.log"
    if source.suffix.lower() == ".csv":
        summary = reporter.summarize_backtest(source)
        text = reporter.render_text(summary, "Backtest Summary")
    else:
        summary = reporter.summarize_log(source)
        text = reporter.render_text(summary, "Log Summary")
    logger.info("\n%s", text)


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    config = load_config(Path(args.config))

    if args.mode == "live":
        if not config["risk"].get("allow_live_trading", False):
            raise PermissionError("Live trading is disabled in config.yaml. Set risk.allow_live_trading=true after demo validation.")
        run_live(config, args.symbol, args.strategy)
    elif args.mode == "report":
        run_report(args.report_source)
    else:
        run_backtest(config, args.symbol, args.strategy, args.csv)


if __name__ == "__main__":
    main()
