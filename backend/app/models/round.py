from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_uuid: Mapped[str] = mapped_column(ForeignKey("games.uuid", ondelete="CASCADE"))
    original_url: Mapped[str] = mapped_column(String(500))
    ai_url: Mapped[str] = mapped_column(String(500))
    solution_text: Mapped[str] = mapped_column(Text)
    target_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_limit: Mapped[int] = mapped_column(Integer, default=20)
    position: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped["Game"] = relationship(back_populates="rounds")
    locations: Mapped[list["Location"]] = relationship(back_populates="round", cascade="all, delete")
    buzzer_events: Mapped[list["BuzzerEvent"]] = relationship(back_populates="round", cascade="all, delete")
    quiz_responses: Mapped[list["QuizResponse"]] = relationship(back_populates="round", cascade="all, delete")
