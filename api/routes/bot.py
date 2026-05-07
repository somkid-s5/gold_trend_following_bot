from fastapi import APIRouter
from pydantic import BaseModel
from api.bot_manager import BotManager

router = APIRouter()
manager = BotManager.get_instance()

class StartRequest(BaseModel):
    mode: str = "live"

class BacktestRequest(BaseModel):
    symbol: str = "XAUUSDm"
    days: int = 365
    balance: float | None = None
    timeframe: str | None = None
    risk: float | None = None
    type: str = "standard"
    dca_amount: float | None = None

@router.post("/start")
async def start_bot(req: StartRequest):
    return manager.start_bot(mode=req.mode)

@router.post("/stop")
async def stop_bot():
    return manager.stop_bot()

@router.get("/status")
async def get_bot_status():
    return {"running": manager.is_running()}

@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    return manager.run_backtest(
        symbol=req.symbol, 
        days=req.days,
        balance=req.balance,
        timeframe=req.timeframe,
        risk=req.risk,
        backtest_type=req.type,
        dca_amount=req.dca_amount
    )
