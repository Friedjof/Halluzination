from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.game import GameStatus


# --- Location ---

class LocationIn(BaseModel):
    name: str
    is_correct: bool = False


class LocationsCreate(BaseModel):
    locations: list[LocationIn]


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    is_correct: Optional[bool] = None


class LocationOut(BaseModel):
    id: int
    name: str
    is_correct: bool

    model_config = {"from_attributes": True}


# --- Round ---

class RoundCreate(BaseModel):
    solution_text: str
    target_year: Optional[int] = None
    time_limit: int = 20
    original_url: str = ""
    ai_url: str = ""


class RoundUpdate(BaseModel):
    solution_text: Optional[str] = None
    target_year: Optional[int] = None
    time_limit: Optional[int] = None
    position: Optional[int] = None


class RoundOut(BaseModel):
    id: int
    original_url: str
    ai_url: str
    original_filename: Optional[str] = None
    ai_filename: Optional[str] = None
    solution_text: str
    target_year: Optional[int] = None
    time_limit: int
    position: int
    locations: list[LocationOut] = []

    model_config = {"from_attributes": True}


class UploadOut(BaseModel):
    original_url: str
    ai_url: str


# --- Participant ---

class ParticipantJoin(BaseModel):
    username: str = Field(min_length=1, max_length=32)

    @field_validator("username")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username darf nicht leer sein")
        return v


class ParticipantOut(BaseModel):
    id: int
    username: str
    score: int
    ready: bool = False
    locked: bool = False

    model_config = {"from_attributes": True}


class ParticipantJoinOut(BaseModel):
    participant_id: int
    username: str
    game_uuid: str


class ScoreUpdate(BaseModel):
    score: int


# --- Game ---

class GameCreate(BaseModel):
    title: str


class GameOut(BaseModel):
    uuid: str
    title: str
    status: GameStatus
    created_at: datetime
    join_url: str

    model_config = {"from_attributes": True}


class GameDetail(GameOut):
    rounds: list[RoundOut] = []
    participants: list[ParticipantOut] = []
