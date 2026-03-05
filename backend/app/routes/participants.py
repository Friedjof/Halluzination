from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_admin
from app.models.game import Game, GameStatus
from app.models.participant import Participant
from app.schemas import ParticipantJoin, ParticipantJoinOut, ParticipantOut, ScoreUpdate

router = APIRouter(prefix="/api/games", tags=["participants"])


@router.post("/{uuid}/join", response_model=ParticipantJoinOut)
async def join_game(uuid: str, body: ParticipantJoin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).where(Game.uuid == uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status == GameStatus.finished:
        raise HTTPException(status_code=409, detail="Game is already finished")

    existing = await db.execute(
        select(Participant).where(Participant.game_uuid == uuid, Participant.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Dieser Name ist bereits vergeben")

    participant = Participant(game_uuid=uuid, username=body.username)
    db.add(participant)
    await db.commit()
    await db.refresh(participant)

    # participant_joined is emitted via the socket join_game event handler,
    # which is more reliable than emitting from an HTTP route handler.
    return ParticipantJoinOut(participant_id=participant.id, username=participant.username, game_uuid=uuid)


@router.get("/{uuid}/participants", response_model=list[ParticipantOut], dependencies=[Depends(require_admin)])
async def list_participants(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Participant).where(Participant.game_uuid == uuid).order_by(Participant.score.desc())
    )
    return [
        ParticipantOut(id=p.id, username=p.username, score=p.score, ready=False, locked=False)
        for p in result.scalars().all()
    ]


@router.delete("/{uuid}/participants/{participant_id}", dependencies=[Depends(require_admin)])
async def kick_participant(uuid: str, participant_id: int, db: AsyncSession = Depends(get_db)):
    """HTTP endpoint kept for API compatibility. Prefer the socket 'kick' admin_action."""
    result = await db.execute(
        select(Participant).where(Participant.id == participant_id, Participant.game_uuid == uuid)
    )
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    await db.delete(participant)
    await db.commit()
    return {"status": "removed"}


@router.patch("/{uuid}/participants/{participant_id}/score", dependencies=[Depends(require_admin)])
async def update_score(uuid: str, participant_id: int, body: ScoreUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Participant).where(Participant.id == participant_id, Participant.game_uuid == uuid)
    )
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    participant.score = body.score
    await db.commit()
    return ParticipantOut(
        id=participant.id,
        username=participant.username,
        score=participant.score,
        ready=False,
        locked=False,
    )
