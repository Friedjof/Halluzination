from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    round: Mapped["Round"] = relationship(back_populates="locations")
    quiz_responses: Mapped[list["QuizResponse"]] = relationship(back_populates="selected_location")
