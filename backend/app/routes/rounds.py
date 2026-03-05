import os
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db, require_admin
from app.models.game import Game
from app.models.location import Location
from app.models.round import Round
from app.schemas import LocationOut, RoundCreate, RoundOut, RoundUpdate, UploadOut

router = APIRouter(prefix="/api/games", tags=["rounds"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


async def _get_round_or_404(uuid: str, round_id: int, db: AsyncSession) -> Round:
    result = await db.execute(
        select(Round)
        .options(selectinload(Round.locations))
        .where(Round.game_uuid == uuid, Round.id == round_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Round not found")
    return r


@router.post("/{uuid}/rounds", response_model=RoundOut, dependencies=[Depends(require_admin)])
async def create_round(uuid: str, body: RoundCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).where(Game.uuid == uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Game not found")

    pos_result = await db.execute(
        select(func.coalesce(func.max(Round.position), -1)).where(Round.game_uuid == uuid)
    )
    next_position = int(pos_result.scalar_one()) + 1

    r = Round(
        game_uuid=uuid,
        original_url=body.original_url,
        ai_url=body.ai_url,
        solution_text=body.solution_text,
        target_year=body.target_year,
        time_limit=body.time_limit,
        position=next_position,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return RoundOut(
        id=r.id,
        original_url=r.original_url,
        ai_url=r.ai_url,
        solution_text=r.solution_text,
        target_year=r.target_year,
        time_limit=r.time_limit,
        position=r.position,
        locations=[],
    )


@router.post("/{uuid}/rounds/{round_id}/upload", response_model=UploadOut, dependencies=[Depends(require_admin)])
async def upload_images(
    uuid: str,
    round_id: int,
    original: UploadFile = File(...),
    ai: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    r = await _get_round_or_404(uuid, round_id, db)

    os.makedirs(settings.upload_dir, exist_ok=True)

    async def _save(file: UploadFile, label: str) -> str:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{label} exceeds 10 MB limit")
        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        filename = f"{_uuid.uuid4().hex}_{label}{ext}"
        path = os.path.join(settings.upload_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
        return f"/uploads/{filename}"

    original_url = await _save(original, "original")
    ai_url = await _save(ai, "ai")

    r.original_url = original_url
    r.ai_url = ai_url
    await db.commit()

    return UploadOut(original_url=original_url, ai_url=ai_url)


@router.patch("/{uuid}/rounds/{round_id}", response_model=RoundOut, dependencies=[Depends(require_admin)])
async def update_round(uuid: str, round_id: int, body: RoundUpdate, db: AsyncSession = Depends(get_db)):
    r = await _get_round_or_404(uuid, round_id, db)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    await db.commit()
    await db.refresh(r)

    return RoundOut(
        id=r.id,
        original_url=r.original_url,
        ai_url=r.ai_url,
        solution_text=r.solution_text,
        target_year=r.target_year,
        time_limit=r.time_limit,
        position=r.position,
        locations=[LocationOut(id=l.id, name=l.name, is_correct=l.is_correct) for l in r.locations],
    )


@router.delete("/{uuid}/rounds/{round_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_round(uuid: str, round_id: int, db: AsyncSession = Depends(get_db)):
    r = await _get_round_or_404(uuid, round_id, db)

    for url in (r.original_url, r.ai_url):
        if url.startswith("/uploads/"):
            path = os.path.join(settings.upload_dir, os.path.basename(url))
            if os.path.exists(path):
                os.remove(path)

    await db.delete(r)
    await db.commit()
