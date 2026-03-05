from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_admin
from app.models.location import Location
from app.models.round import Round
from app.schemas import LocationOut, LocationsCreate, LocationUpdate

router = APIRouter(prefix="/api/rounds", tags=["locations"])


@router.post("/{round_id}/locations", response_model=list[LocationOut], dependencies=[Depends(require_admin)])
async def create_locations(round_id: int, body: LocationsCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Round).where(Round.id == round_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Round not found")

    correct_count = sum(1 for loc in body.locations if loc.is_correct)
    if correct_count != 1:
        raise HTTPException(status_code=422, detail="Exactly one location must be correct")

    locations = [Location(round_id=round_id, name=loc.name, is_correct=loc.is_correct) for loc in body.locations]
    db.add_all(locations)
    await db.commit()
    for loc in locations:
        await db.refresh(loc)
    return [LocationOut(id=l.id, name=l.name, is_correct=l.is_correct) for l in locations]


@router.delete("/{round_id}/locations", status_code=204, dependencies=[Depends(require_admin)])
async def delete_locations(round_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Round).where(Round.id == round_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Round not found")
    await db.execute(sa_delete(Location).where(Location.round_id == round_id))
    await db.commit()


@router.patch("/{round_id}/locations/{loc_id}", response_model=LocationOut, dependencies=[Depends(require_admin)])
async def update_location(round_id: int, loc_id: int, body: LocationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Location).where(Location.id == loc_id, Location.round_id == round_id)
    )
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(loc, field, value)
    await db.commit()
    await db.refresh(loc)
    return LocationOut(id=loc.id, name=loc.name, is_correct=loc.is_correct)
