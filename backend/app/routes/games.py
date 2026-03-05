from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db, require_admin
from app.models.game import Game, GameStatus
from app.models.location import Location
from app.models.round import Round
from app.schemas import GameCreate, GameDetail, GameOut, ParticipantOut, RoundOut, LocationOut

router = APIRouter(prefix="/api/games", tags=["games"])


def _join_url(uuid: str) -> str:
    return f"{settings.frontend_url}/play/{uuid}"


@router.post("", response_model=GameOut, dependencies=[Depends(require_admin)])
async def create_game(body: GameCreate, db: AsyncSession = Depends(get_db)):
    game = Game(title=body.title)
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return GameOut(
        uuid=game.uuid,
        title=game.title,
        status=game.status,
        created_at=game.created_at,
        join_url=_join_url(game.uuid),
    )


@router.get("/{uuid}", response_model=GameDetail, dependencies=[Depends(require_admin)])
async def get_game(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Game)
        .options(
            selectinload(Game.rounds).selectinload(Round.locations),
            selectinload(Game.participants),
        )
        .where(Game.uuid == uuid)
    )
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return GameDetail(
        uuid=game.uuid,
        title=game.title,
        status=game.status,
        created_at=game.created_at,
        join_url=_join_url(game.uuid),
        rounds=[
            RoundOut(
                id=r.id,
                original_url=r.original_url,
                ai_url=r.ai_url,
                solution_text=r.solution_text,
                target_year=r.target_year,
                time_limit=r.time_limit,
                position=r.position,
                locations=[LocationOut(id=l.id, name=l.name, is_correct=l.is_correct) for l in r.locations],
            )
            for r in game.rounds
        ],
        participants=[
            ParticipantOut(id=p.id, username=p.username, score=p.score)
            for p in game.participants
        ],
    )


@router.post("/{uuid}/start", dependencies=[Depends(require_admin)])
async def start_game(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).where(Game.uuid == uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=409, detail="Game is not in lobby state")
    game.status = GameStatus.active
    await db.commit()
    return {"status": "active"}


@router.post("/{uuid}/end", dependencies=[Depends(require_admin)])
async def end_game(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).where(Game.uuid == uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    game.status = GameStatus.finished
    await db.commit()
    return {"status": "finished"}
