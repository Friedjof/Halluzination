import os

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import auth, games, locations, participants, rounds
from app.socket.manager import sio
import app.socket.events  # noqa: F401 – registers all event handlers

fastapi_app = FastAPI(title="Halluzination")

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(auth.router)
fastapi_app.include_router(games.router)
fastapi_app.include_router(rounds.router)
fastapi_app.include_router(locations.router)
fastapi_app.include_router(participants.router)

os.makedirs(settings.upload_dir, exist_ok=True)
fastapi_app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@fastapi_app.get("/health")
async def health():
    return {"status": "ok"}


# Combined ASGI app: socket.io wraps FastAPI
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
