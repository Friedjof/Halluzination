from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BuzzerEvent(Base):
    __tablename__ = "buzzer_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"))
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)

    round: Mapped["Round"] = relationship(back_populates="buzzer_events")
    participant: Mapped["Participant"] = relationship(back_populates="buzzer_events")
