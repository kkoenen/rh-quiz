from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import init_db
from app.routers import user, quiz, leaderboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RH Quiz",
    description="Red Hat Quiz Application",
    version="1.0.0",
    lifespan=lifespan,
)

# Routers
app.include_router(user.router)
app.include_router(quiz.router)
app.include_router(leaderboard.router)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok"}
