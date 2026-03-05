from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuizResponse(Base):
    __tablename__ = "quiz_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"))
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    selected_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    year_guess: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)

    round: Mapped["Round"] = relationship(back_populates="quiz_responses")
    participant: Mapped["Participant"] = relationship(back_populates="quiz_responses")
    selected_location: Mapped["Location"] = relationship(back_populates="quiz_responses")
