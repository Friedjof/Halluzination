import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GameStatus(enum.Enum):
    lobby = "lobby"
    active = "active"
    finished = "finished"


class Game(Base):
    __tablename__ = "games"

    uuid: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[GameStatus] = mapped_column(Enum(GameStatus), default=GameStatus.lobby)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    participants: Mapped[list["Participant"]] = relationship(back_populates="game")
    rounds: Mapped[list["Round"]] = relationship(back_populates="game", order_by="Round.position")
