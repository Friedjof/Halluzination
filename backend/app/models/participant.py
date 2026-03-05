from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("game_uuid", "username", name="uq_participant_game_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_uuid: Mapped[str] = mapped_column(ForeignKey("games.uuid", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(String(100))
    score: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped["Game"] = relationship(back_populates="participants")
    buzzer_events: Mapped[list["BuzzerEvent"]] = relationship(back_populates="participant")
    quiz_responses: Mapped[list["QuizResponse"]] = relationship(back_populates="participant")
