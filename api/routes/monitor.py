from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
from typing import Any

router = APIRouter()
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

@router.get("/logs")
async def get_logs(lines: int = 50) -> dict[str, Any]:
    log_path = ROOT_DIR / "logs" / "gold_trading_bot.log"
    if not log_path.exists():
        return {"logs": []}
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return {"logs": [line.strip() for line in all_lines[-lines:]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_system_status() -> dict[str, Any]:
    reports_dir = ROOT_DIR / "reports"
    status = {}
    
    # Read Guard Status
    guard_path = reports_dir / "guard_status.json"
    if guard_path.exists():
        try:
            with open(guard_path, "r", encoding="utf-8") as f:
                status["guard"] = json.load(f)
        except:
            status["guard"] = None
            
    # Read Runtime Status
    runtime_path = reports_dir / "runtime_status.json"
    if runtime_path.exists():
        try:
            with open(runtime_path, "r", encoding="utf-8") as f:
                status["runtime"] = json.load(f)
        except:
            status["runtime"] = None
            
    return status

@router.get("/trades")
async def get_trades() -> list[dict[str, Any]]:
    history_path = ROOT_DIR / "reports" / "trade_history.json"
    if not history_path.exists():
        return []
    
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []
