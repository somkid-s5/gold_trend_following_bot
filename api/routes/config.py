from fastapi import APIRouter, HTTPException
import yaml
from pathlib import Path
from typing import Any

router = APIRouter()
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"

@router.get("/")
async def get_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/")
async def update_config(new_config: dict[str, Any]) -> dict[str, str]:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    try:
        # We might want to preserve comments, but yaml.safe_dump removes them.
        # For a full webapp, this is usually acceptable, or we can use ruamel.yaml.
        # We'll use pyyaml for now.
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_config, f, default_flow_style=False, sort_keys=False)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
