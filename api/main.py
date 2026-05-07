from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.routes import bot, config, monitor

ROOT_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="TITAN Berserker API",
    version="3.0.0",
    description="API for the TITAN Gold Trend Following Trading Bot",
)

# CORS — allows local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(bot.router, prefix="/api/bot", tags=["Bot Control"])
app.include_router(config.router, prefix="/api/config", tags=["Configuration"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["Monitoring"])

# In production, serve the built frontend
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {
            "message": "TITAN Berserker API is running",
            "docs": "/docs",
            "note": "Build the frontend with 'npm run build' to serve it here.",
        }

if __name__ == "__main__":
    import uvicorn
    # access_log=False reduces noise from constant polling
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
