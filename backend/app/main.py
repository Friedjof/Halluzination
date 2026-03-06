import os

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.routes import auth, export_import, games, locations, participants, rounds
from app.socket.manager import sio
import app.socket.events  # noqa: F401 – registers all event handlers

limiter = Limiter(key_func=get_remote_address)

fastapi_app = FastAPI(title="Halluzination")
fastapi_app.state.limiter = limiter
fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(auth.router)
fastapi_app.include_router(export_import.router)  # before games so /import beats /{uuid}
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
