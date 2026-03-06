import io
import json
import os
import uuid as _uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db, require_admin
from app.models.game import Game
from app.models.location import Location
from app.models.round import Round

router = APIRouter(prefix="/api/games", tags=["export"])

FORMAT_VERSION = "1"


def _export_filename(stored_url: str, original_filename: str | None, label: str) -> str:
    """Return a unique archive filename: <stem>.<5-char-random><ext>"""
    suffix = _uuid.uuid4().hex[:5]
    if original_filename:
        p = Path(original_filename)
        return f"{p.stem}.{suffix}{p.suffix}"
    ext = Path(os.path.basename(stored_url)).suffix or ".jpg"
    return f"{label}.{suffix}{ext}"


def _disk_path(url: str) -> str:
    if url.startswith("/uploads/"):
        return os.path.join(settings.upload_dir, os.path.basename(url))
    return url


@router.get("/{uuid}/export", dependencies=[Depends(require_admin)])
async def export_game(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Game)
        .options(selectinload(Game.rounds).selectinload(Round.locations))
        .where(Game.uuid == uuid)
    )
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    rounds_sorted = sorted(game.rounds, key=lambda r: r.position)

    rounds_data = []
    image_entries: list[tuple[str, str]] = []  # (archive_path, disk_path)

    for r in rounds_sorted:
        orig_name = _export_filename(r.original_url, r.original_filename, "original")
        ai_name = _export_filename(r.ai_url, r.ai_filename, "ai")

        rounds_data.append({
            "position": r.position,
            "solution_text": r.solution_text,
            "target_year": r.target_year,
            "time_limit": r.time_limit,
            "original_image": f"images/{orig_name}",
            "ai_image": f"images/{ai_name}",
            "locations": [
                {"name": loc.name, "is_correct": loc.is_correct}
                for loc in sorted(r.locations, key=lambda l: l.id)
            ],
        })
        image_entries.append((f"images/{orig_name}", _disk_path(r.original_url)))
        image_entries.append((f"images/{ai_name}", _disk_path(r.ai_url)))

    export_data = {
        "format_version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "game": {"title": game.title},
        "rounds": rounds_data,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.json", json.dumps(export_data, ensure_ascii=False, indent=2))
        for archive_path, dpath in image_entries:
            if os.path.exists(dpath):
                zf.write(dpath, archive_path)

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in game.title)[:40]
    filename = f"halluzination_{safe_title}_export.zip"
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", dependencies=[Depends(require_admin)])
async def import_game(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Ungültige ZIP-Datei")

    try:
        export_data = json.loads(zf.read("export.json"))
    except KeyError:
        raise HTTPException(status_code=400, detail="export.json nicht gefunden")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="export.json ist ungültig")

    game_meta = export_data.get("game", {})
    rounds_data: list[dict] = export_data.get("rounds", [])

    new_game = Game(title=game_meta.get("title", "Importiertes Spiel"))
    db.add(new_game)
    await db.flush()

    os.makedirs(settings.upload_dir, exist_ok=True)

    for rd in sorted(rounds_data, key=lambda r: r.get("position", 0)):
        def _save(archive_path: str, label: str) -> tuple[str, str]:
            try:
                img_bytes = zf.read(archive_path)
            except KeyError:
                raise HTTPException(
                    status_code=400, detail=f"Bild nicht gefunden: {archive_path}"
                )
            ext = Path(archive_path).suffix or ".jpg"
            fname = f"{_uuid.uuid4().hex}_{label}{ext}"
            with open(os.path.join(settings.upload_dir, fname), "wb") as fh:
                fh.write(img_bytes)
            return f"/uploads/{fname}", Path(archive_path).name

        orig_url, orig_fname = _save(rd["original_image"], "original")
        ai_url, ai_fname = _save(rd["ai_image"], "ai")

        new_round = Round(
            game_uuid=new_game.uuid,
            original_url=orig_url,
            ai_url=ai_url,
            original_filename=orig_fname,
            ai_filename=ai_fname,
            solution_text=rd.get("solution_text", ""),
            target_year=rd.get("target_year"),
            time_limit=rd.get("time_limit", 20),
            position=rd.get("position", 0),
        )
        db.add(new_round)
        await db.flush()

        for loc in rd.get("locations", []):
            db.add(Location(
                round_id=new_round.id,
                name=loc["name"],
                is_correct=loc.get("is_correct", False),
            ))

    await db.commit()
    return {"uuid": new_game.uuid, "title": new_game.title}
