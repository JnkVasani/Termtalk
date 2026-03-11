"""
TermTalk Server - Main Entry Point
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from server.database.db import init_db
from server.api.routes import router as api_router
from server.websocket.manager import router as ws_router
from server.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_db()
    print(f"🚀 TermTalk Server starting on {settings.HOST}:{settings.PORT}")
    yield
    print("👋 TermTalk Server shutting down")


app = FastAPI(
    title="TermTalk Server",
    description="Real-time CLI communication platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TermTalk Server", "version": "1.0.0"}


def run():
    uvicorn.run(
        "server.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
@app.get("/")
async def root():
    return {
        "service": "TermTalk Server",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    run()
