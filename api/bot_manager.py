from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

class BotManager:
    _instance = None
    _process: subprocess.Popen | None = None
    
    @classmethod
    def get_instance(cls) -> BotManager:
        if cls._instance is None:
            cls._instance = BotManager()
        return cls._instance

    def start_bot(self, mode: str = "live") -> dict[str, Any]:
        if self.is_running():
            return {"status": "error", "message": "Bot is already running"}
            
        script_path = ROOT_DIR / "main.py"
        if not script_path.exists():
            return {"status": "error", "message": "main.py not found"}

        # Run via python executable
        cmd = ["python", str(script_path), "--mode", mode]
        
        try:
            # We don't pipe stdout/stderr here, we let it write to the logger file
            # or we could pipe it if we wanted to read it directly, but logger writes to logs/
            # and that's better for persistence.
            self._process = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                # CREATE_NEW_PROCESS_GROUP is needed on Windows to send CTRL_BREAK_EVENT
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            # Append start marker to log
            try:
                log_file = ROOT_DIR / "logs" / "gold_trading_bot.log"
                log_file.parent.mkdir(exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as f:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                    f.write(f"{timestamp} | INFO | SYSTEM | ENGINE STARTED (Mode: {mode})\n")
            except:
                pass
                
            return {"status": "success", "message": f"Bot started in {mode} mode", "pid": self._process.pid}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run_backtest(self, symbol: str, days: int, balance: float | None = None, timeframe: str | None = None, risk: float | None = None, backtest_type: str = "standard", dca_amount: float | None = None) -> dict[str, Any]:
        script_path = ROOT_DIR / "scripts" / "run_backtest.py"
        if not script_path.exists():
            return {"status": "error", "message": "Backtest script not found"}

        cmd = ["python", str(script_path), "--type", backtest_type, "--days", str(days)]
        if symbol: cmd.extend(["--symbol", symbol])
        if balance: cmd.extend(["--balance", str(balance)])
        if dca_amount: cmd.extend(["--dca", str(dca_amount)])
        if risk: cmd.extend(["--risk", str(risk)])
        
        try:
            subprocess.run(cmd, cwd=str(ROOT_DIR), check=True, capture_output=True, text=True)
            
            reports_dir = ROOT_DIR / "reports"
            if backtest_type == "dca":
                reports = list(reports_dir.glob("dca_report_*.json"))
            else:
                reports = list(reports_dir.glob(f"backtest_{symbol}_*.json"))
                
            if not reports:
                return {"status": "error", "message": "Backtest finished but no report was generated"}
            
            latest_report = max(reports, key=os.path.getmtime)
            import json
            with open(latest_report, "r", encoding="utf-8") as f:
                result = json.load(f)
                
            return {"status": "success", "data": result}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Backtest failed: {e.stderr}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop_bot(self) -> dict[str, Any]:
        if not self.is_running():
            return {"status": "error", "message": "Bot is not running"}
            
        try:
            if os.name == 'nt':
                # Send CTRL_BREAK_EVENT to gracefully terminate
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()
                
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    # Fallback to taskkill if signal didn't work
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._process.pid)], capture_output=True)
                else:
                    self._process.kill()
                
            self._process = None
            
            # Append stop marker to log
            try:
                log_file = ROOT_DIR / "logs" / "gold_trading_bot.log"
                if log_file.exists():
                    with open(log_file, "a", encoding="utf-8") as f:
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                        f.write(f"{timestamp} | INFO | SYSTEM | ENGINE STOPPED BY USER\n")
            except:
                pass
                
            return {"status": "success", "message": "Bot stopped gracefully"}
        except Exception as e:
            # Fallback hard kill
            if self._process:
                try:
                    if os.name == 'nt':
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._process.pid)], capture_output=True)
                    else:
                        self._process.kill()
                except:
                    pass
                self._process = None
            return {"status": "error", "message": f"Error stopping bot: {e}"}

    def is_running(self) -> bool:
        # 1. Check internal process state
        if self._process is not None:
            if self._process.poll() is None:
                return True
            self._process = None

        # 2. Check for PID file (manually started)
        pid_file = ROOT_DIR / "logs" / "bot.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text())
                if os.name == 'nt':
                    # Windows check for PID
                    import ctypes
                    PROCESS_QUERY_INFORMATION = 0x0400
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                        return True
                else:
                    # Linux/Mac check for PID
                    os.kill(pid, 0)
                    return True
            except:
                # If error (invalid PID or no access), assume not running or stale
                pass
                
        return False
