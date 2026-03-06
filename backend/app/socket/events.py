import asyncio
import logging
import time

from sqlalchemy import and_, delete as sa_delete, or_, select, func

logger = logging.getLogger(__name__)
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.game import Game, GameStatus
from app.models.location import Location
from app.models.participant import Participant
from app.models.quiz_response import QuizResponse
from app.models.round import Round
from app.redis_client import (
    clear_buzzer,
    clear_game_state,
    clear_lobby_ready,
    get_buzzer,
    get_locked_set,
    get_lobby_ready_count,
    get_lobby_ready_set,
    get_participant_sid,
    get_sid_info,
    is_locked,
    lock_participant,
    mark_lobby_ready,
    remove_sid,
    set_game_state,
    get_game_state_field,
    set_participant_sid,
    try_lock_buzzer,
    unlock_all_participants,
    unlock_participant,
)
from app.socket.manager import sio

# Tracks active quiz-close tasks: key = f"{game_uuid}:{round_id}"
_quiz_tasks: dict[str, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _emit_participants_update(game_uuid: str, to: str | None = None) -> None:
    """Fetch the full participant list + lobby-ready state and push it.

    If `to` is a SID, only that client receives the update (used on join so
    the newcomer immediately sees the current state).  Otherwise the entire
    game room receives the update.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Participant)
            .where(Participant.game_uuid == game_uuid)
            .order_by(Participant.id)
        )
        db_participants = result.scalars().all()

    ready_ids = await get_lobby_ready_set(game_uuid)
    locked_ids = await get_locked_set(game_uuid)

    payload = {
        "participants": [
            {
                "id": p.id,
                "username": p.username,
                "score": p.score,
                "ready": p.id in ready_ids,
                "locked": p.id in locked_ids,
            }
            for p in db_participants
        ]
    }

    if to:
        await sio.emit("participants_update", payload, to=to)
    else:
        await sio.emit("participants_update", payload, room=f"game:{game_uuid}")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@sio.event
async def connect(sid, environ):
    pass  # actual join happens via join_game / join_admin / join_present


@sio.event
async def disconnect(sid):
    await remove_sid(sid)


@sio.on("join_game")
async def handle_join_game(sid, data):
    """Participant joins a game room. data: {game_uuid, participant_id}"""
    game_uuid = data.get("game_uuid")
    participant_id = data.get("participant_id")
    if not game_uuid or not participant_id:
        return

    participant_id = int(participant_id)

    # Verify participant still exists – rejects kicked players trying to reconnect
    async with AsyncSessionLocal() as db:
        p_check = await db.execute(
            select(Participant).where(Participant.id == participant_id, Participant.game_uuid == game_uuid)
        )
        if not p_check.scalar_one_or_none():
            await sio.emit("kicked", {}, to=sid)
            return

    await sio.enter_room(sid, f"game:{game_uuid}")
    await set_participant_sid(game_uuid, participant_id, sid)
    participant_locked = await is_locked(game_uuid, participant_id)

    # Build the joined response (include current round for late joiners)
    response: dict = {
        "game_uuid": game_uuid,
        "participant_id": participant_id,
        "locked": participant_locked,
    }
    current_round_id = await get_game_state_field(game_uuid, "current_round_id")
    if current_round_id:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Round).where(Round.id == int(current_round_id)))
            r = result.scalar_one_or_none()
            if r:
                response["current_round_id"] = r.id
                response["ai_image_url"] = r.ai_url

    # Include current buzzer-sound preference so late joiners/reconnectors are in sync
    buzzer_sound_raw = await get_game_state_field(game_uuid, "buzzer_sound")
    response["buzzer_sound_enabled"] = buzzer_sound_raw != "0"

    logger.info("join_game game=%s participant_id=%s", game_uuid, participant_id)
    await sio.emit("joined", response, to=sid)

    # Broadcast the updated full participant list to the whole game room.
    # This is the single source of truth for admin and presentation views.
    await _emit_participants_update(game_uuid)


@sio.on("join_present")
async def handle_join_present(sid, data):
    """Presentation screen joins a game room as observer. data: {game_uuid}"""
    game_uuid = data.get("game_uuid")
    if not game_uuid:
        return
    await sio.enter_room(sid, f"game:{game_uuid}")
    await sio.emit("joined_present", {"game_uuid": game_uuid}, to=sid)

    # Re-sync presentation state after reload/reconnect.
    current_round_id = await get_game_state_field(game_uuid, "current_round_id")
    present_phase = await get_game_state_field(game_uuid, "present_phase")
    if current_round_id:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Round).options(selectinload(Round.locations)).where(Round.id == int(current_round_id))
            )
            r = result.scalar_one_or_none()
            if r:
                if present_phase == "revealed":
                    correct_location = next((loc for loc in r.locations if loc.is_correct), None)
                    await sio.emit(
                        "round_end",
                        {
                            "round_id": r.id,
                            "original_url": r.original_url,
                            "ai_url": r.ai_url,
                            "solution_text": r.solution_text,
                            "target_year": r.target_year,
                            "correct_location": correct_location.name if correct_location else None,
                        },
                        to=sid,
                    )
                elif present_phase == "quiz":
                    await sio.emit(
                        "round_start",
                        {"round_id": r.id, "ai_image_url": r.ai_url},
                        to=sid,
                    )
                    ends_at_raw = await get_game_state_field(game_uuid, "quiz_ends_at")
                    now_ts = int(time.time())
                    if ends_at_raw and ends_at_raw.isdigit():
                        remaining = max(0, int(ends_at_raw) - now_ts)
                    else:
                        remaining = r.time_limit
                    await sio.emit(
                        "quiz_start",
                        {"locations": [], "time_limit": remaining, "round_id": r.id},
                        to=sid,
                    )
                else:
                    await sio.emit(
                        "round_start",
                        {"round_id": r.id, "ai_image_url": r.ai_url},
                        to=sid,
                    )

    # Send the current participant list so the screen is up to date immediately
    await _emit_participants_update(game_uuid, to=sid)


@sio.on("join_admin")
async def handle_join_admin(sid, data):
    """Admin joins the admin room. data: {game_uuid, admin_token}"""
    if data.get("admin_token") != settings.admin_token:
        await sio.emit("error", {"message": "Unauthorized"}, to=sid)
        return
    game_uuid = data.get("game_uuid")
    await sio.enter_room(sid, f"game:{game_uuid}")
    await sio.enter_room(sid, f"admin:{game_uuid}")
    await sio.emit("joined_admin", {"game_uuid": game_uuid}, to=sid)
    # Send the current participant list so the admin panel is up to date immediately
    await _emit_participants_update(game_uuid, to=sid)


@sio.on("lobby_ready")
async def handle_lobby_ready(sid, data):
    """Participant signals ready in lobby."""
    info = await get_sid_info(sid)
    if not info:
        return
    game_uuid = info["game_uuid"]
    participant_id = int(info["participant_id"])
    await mark_lobby_ready(game_uuid, participant_id)

    # Broadcast updated list (ready flag changed) to the whole room
    await _emit_participants_update(game_uuid)



# ---------------------------------------------------------------------------
# Buzzer
# ---------------------------------------------------------------------------

@sio.on("buzz")
async def handle_buzz(sid, data):
    """data: {round_id}"""
    info = await get_sid_info(sid)
    if not info:
        return
    game_uuid = info["game_uuid"]
    participant_id = int(info["participant_id"])
    round_id = int(data.get("round_id", 0))

    # Validate participant exists and belongs to this game
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Participant).where(
                Participant.id == participant_id,
                Participant.game_uuid == game_uuid,
            )
        )
        participant = result.scalar_one_or_none()
        if not participant:
            return
        username = participant.username

    if await is_locked(game_uuid, participant_id):
        return

    won = await try_lock_buzzer(game_uuid, round_id, participant_id)
    if not won:
        logger.debug("buzz lost game=%s round=%s participant=%s", game_uuid, round_id, participant_id)
        return
    logger.info("buzz won game=%s round=%s participant=%s", game_uuid, round_id, participant_id)

    await sio.emit("buzz_confirmed", {"participant_id": participant_id}, to=sid)
    await sio.emit(
        "buzz_received",
        {"participant_id": participant_id, "username": username, "round_id": round_id},
        room=f"admin:{game_uuid}",
    )
    await sio.emit(
        "lockout",
        {"winner_id": participant_id, "winner_name": username},
        room=f"game:{game_uuid}",
        skip_sid=sid,
    )


# ---------------------------------------------------------------------------
# Admin actions
# ---------------------------------------------------------------------------

@sio.on("admin_action")
async def handle_admin_action(sid, data):
    """
    data: {game_uuid, admin_token, action, participant_id?, round_id?}
    Actions: correct | wrong | unlock | unlock_all | next_round | reveal | skip | kick | end_game
    """
    if data.get("admin_token") != settings.admin_token:
        await sio.emit("error", {"message": "Unauthorized"}, to=sid)
        return

    action = data.get("action")
    game_uuid = data.get("game_uuid")
    participant_id = data.get("participant_id")
    round_id = data.get("round_id")

    if action == "correct":
        await _handle_correct(game_uuid, round_id, participant_id)
    elif action == "wrong":
        await _handle_wrong(game_uuid, round_id, participant_id)
    elif action == "unlock":
        await _handle_unlock(game_uuid, participant_id)
    elif action == "unlock_all":
        await _handle_unlock_all(game_uuid, round_id)
    elif action == "next_round":
        await _handle_next_round(game_uuid)
    elif action == "reveal":
        await _handle_reveal(game_uuid, round_id)
    elif action == "skip":
        await _handle_skip(game_uuid, round_id)
    elif action == "kick":
        await _handle_kick(game_uuid, participant_id)
    elif action == "set_score":
        await _handle_set_score(game_uuid, participant_id, data.get("score"))
    elif action == "set_buzzer_sound":
        await _handle_set_buzzer_sound(game_uuid, data.get("enabled", True))
    elif action == "reset_game":
        await _handle_reset_game(game_uuid)
    elif action == "end_game":
        await _handle_end_game(game_uuid)


async def _handle_correct(game_uuid: str, round_id: int, participant_id: int):
    logger.info("correct game=%s round=%s participant=%s", game_uuid, round_id, participant_id)
    # Fetch data first without committing score yet
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Participant).where(Participant.id == participant_id))
        if not result.scalar_one_or_none():
            return

        round_result = await db.execute(
            select(Round).options(selectinload(Round.locations)).where(Round.id == round_id)
        )
        r = round_result.scalar_one_or_none()
        if not r:
            return

        locations = [{"id": l.id, "name": l.name} for l in r.locations]

    has_quiz = bool(r.locations) or r.target_year is not None

    # Persist the score (+2 for correct buzzer)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Participant).where(Participant.id == participant_id))
        participant = result.scalar_one_or_none()
        if participant:
            participant.score += 2
            await db.commit()

    if not has_quiz:
        # No quiz configured – award points and reveal immediately
        logger.info("no quiz configured for round=%s, revealing directly", round_id)
        await _emit_participants_update(game_uuid)
        await _handle_reveal(game_uuid, round_id)
        return

    # Set Redis state first so quiz is atomically "started" before score is persisted
    await set_game_state(
        game_uuid,
        buzzed_participant_id=participant_id,
        quiz_active=1,
        present_phase="quiz",
        quiz_ends_at=int(time.time()) + r.time_limit,
    )

    await sio.emit(
        "quiz_start",
        {"locations": locations, "time_limit": r.time_limit, "round_id": round_id},
        room=f"game:{game_uuid}",
    )

    key = f"{game_uuid}:{round_id}"
    if key in _quiz_tasks:
        _quiz_tasks[key].cancel()
    _quiz_tasks[key] = asyncio.create_task(_close_quiz_after(game_uuid, round_id, r.time_limit))


async def _handle_wrong(game_uuid: str, round_id: int, participant_id: int):
    logger.info("wrong game=%s round=%s participant=%s", game_uuid, round_id, participant_id)
    await lock_participant(game_uuid, participant_id)
    await clear_buzzer(game_uuid, round_id)

    locked_ids = await get_locked_set(game_uuid)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Participant.id).where(Participant.game_uuid == game_uuid)
        )
        participant_ids = [row[0] for row in result.all()]

    for pid in participant_ids:
        p_sid = await get_participant_sid(game_uuid, pid)
        if not p_sid:
            continue
        if pid in locked_ids:
            await sio.emit("lockout", {"reason": "wrong"}, to=p_sid)
        else:
            await sio.emit("unlock", {"message": "buzzer reset"}, to=p_sid)

    await _emit_participants_update(game_uuid)


async def _handle_unlock(game_uuid: str, participant_id: int):
    await unlock_participant(game_uuid, participant_id)
    p_sid = await get_participant_sid(game_uuid, int(participant_id))
    if p_sid:
        await sio.emit("unlock", {}, to=p_sid)
    await _emit_participants_update(game_uuid)


async def _handle_unlock_all(game_uuid: str, round_id: int | None):
    await unlock_all_participants(game_uuid)
    if round_id:
        await clear_buzzer(game_uuid, round_id)
    await sio.emit("unlock_all", {}, room=f"game:{game_uuid}")
    await _emit_participants_update(game_uuid)


async def _handle_next_round(game_uuid: str):
    logger.info("next_round game=%s", game_uuid)
    async with AsyncSessionLocal() as db:
        current_id = await get_game_state_field(game_uuid, "current_round_id")

        if current_id:
            current_round_result = await db.execute(
                select(Round.id, Round.position)
                .where(Round.id == int(current_id), Round.game_uuid == game_uuid)
                .limit(1)
            )
            current_round = current_round_result.one_or_none()

            if current_round is None:
                result = await db.execute(
                    select(Round)
                    .where(Round.game_uuid == game_uuid)
                    .order_by(Round.position.asc(), Round.id.asc())
                    .limit(1)
                )
            else:
                current_round_id, current_position = current_round
                result = await db.execute(
                    select(Round)
                    .where(
                        Round.game_uuid == game_uuid,
                        or_(
                            Round.position > current_position,
                            and_(Round.position == current_position, Round.id > current_round_id),
                        ),
                    )
                    .order_by(Round.position.asc(), Round.id.asc())
                    .limit(1)
                )
        else:
            result = await db.execute(
                select(Round)
                .where(Round.game_uuid == game_uuid)
                .order_by(Round.position.asc(), Round.id.asc())
                .limit(1)
            )
        next_round = result.scalar_one_or_none()

    if not next_round:
        logger.info("no more rounds, ending game=%s", game_uuid)
        await sio.emit("game_end", {}, room=f"game:{game_uuid}")
        return
    logger.info("starting round=%s game=%s", next_round.id, game_uuid)

    await unlock_all_participants(game_uuid)
    await clear_buzzer(game_uuid, next_round.id)
    await set_game_state(game_uuid, current_round_id=next_round.id, quiz_active=0, present_phase="round", quiz_ends_at=0)
    await _emit_participants_update(game_uuid)

    await sio.emit(
        "round_start",
        {"round_id": next_round.id, "ai_image_url": next_round.ai_url},
        room=f"game:{game_uuid}",
    )


async def _handle_reveal(game_uuid: str, round_id: int):
    key = f"{game_uuid}:{round_id}"
    if key in _quiz_tasks:
        _quiz_tasks[key].cancel()
        _quiz_tasks.pop(key, None)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Round).options(selectinload(Round.locations)).where(Round.id == round_id)
        )
        r = result.scalar_one_or_none()
        if not r:
            return

    await set_game_state(game_uuid, present_phase="revealed")
    correct_location = next((loc for loc in r.locations if loc.is_correct), None)

    await sio.emit(
        "round_end",
        {
            "round_id": round_id,
            "original_url": r.original_url,
            "ai_url": r.ai_url,
            "solution_text": r.solution_text,
            "target_year": r.target_year,
            "correct_location": correct_location.name if correct_location else None,
        },
        room=f"game:{game_uuid}",
    )


async def _handle_skip(game_uuid: str, round_id: int):
    await _handle_reveal(game_uuid, round_id)


async def _handle_kick(game_uuid: str, participant_id: int):
    logger.info("kick game=%s participant=%s", game_uuid, participant_id)
    participant_id = int(participant_id)
    p_sid = await get_participant_sid(game_uuid, participant_id)
    if p_sid:
        await sio.emit("kicked", {}, to=p_sid)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Participant)
            .where(Participant.id == participant_id, Participant.game_uuid == game_uuid)
        )
        participant = result.scalar_one_or_none()
        if participant:
            await db.delete(participant)
            await db.commit()

    # Broadcast updated list so every observer removes the kicked player
    await _emit_participants_update(game_uuid)


async def _handle_set_buzzer_sound(game_uuid: str, enabled: bool) -> None:
    logger.info("set_buzzer_sound game=%s enabled=%s", game_uuid, enabled)
    await set_game_state(game_uuid, buzzer_sound=1 if enabled else 0)
    await sio.emit("buzzer_sound", {"enabled": enabled}, room=f"game:{game_uuid}")


async def _handle_set_score(game_uuid: str, participant_id: int, score) -> None:
    if score is None:
        return
    logger.info("set_score game=%s participant=%s score=%s", game_uuid, participant_id, score)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Participant).where(
                Participant.id == int(participant_id),
                Participant.game_uuid == game_uuid,
            )
        )
        participant = result.scalar_one_or_none()
        if not participant:
            return
        participant.score = int(score)
        await db.commit()
    await _emit_participants_update(game_uuid)


async def _handle_reset_game(game_uuid: str):
    logger.info("reset_game game=%s", game_uuid)
    # Cancel any running quiz tasks for this game
    for key in list(_quiz_tasks.keys()):
        if key.startswith(f"{game_uuid}:"):
            _quiz_tasks[key].cancel()
            _quiz_tasks.pop(key, None)

    async with AsyncSessionLocal() as db:
        rounds_result = await db.execute(select(Round.id).where(Round.game_uuid == game_uuid))
        round_ids = [row[0] for row in rounds_result.all()]

        if round_ids:
            await db.execute(sa_delete(QuizResponse).where(QuizResponse.round_id.in_(round_ids)))

        participants_result = await db.execute(
            select(Participant).where(Participant.game_uuid == game_uuid)
        )
        for p in participants_result.scalars().all():
            p.score = 0

        game_result = await db.execute(select(Game).where(Game.uuid == game_uuid))
        game = game_result.scalar_one_or_none()
        if game:
            game.status = GameStatus.lobby

        await db.commit()

    await clear_game_state(game_uuid)
    await clear_lobby_ready(game_uuid)
    await unlock_all_participants(game_uuid)
    for rid in round_ids:
        await clear_buzzer(game_uuid, rid)

    await sio.emit("game_reset", {}, room=f"game:{game_uuid}")
    await _emit_participants_update(game_uuid)


async def _handle_end_game(game_uuid: str):
    logger.info("end_game game=%s", game_uuid)
    for key in list(_quiz_tasks.keys()):
        if key.startswith(f"{game_uuid}:"):
            _quiz_tasks[key].cancel()
            _quiz_tasks.pop(key, None)

    async with AsyncSessionLocal() as db:
        rounds_result = await db.execute(select(Round.id).where(Round.game_uuid == game_uuid))
        round_ids = [row[0] for row in rounds_result.all()]

        result = await db.execute(select(Game).where(Game.uuid == game_uuid))
        game = result.scalar_one_or_none()
        if game:
            game.status = GameStatus.lobby
            await db.commit()

        participants_result = await db.execute(
            select(Participant)
            .where(Participant.game_uuid == game_uuid)
            .order_by(Participant.score.desc())
        )
        final_leaderboard = [
            {"participant_id": p.id, "username": p.username, "score": p.score}
            for p in participants_result.scalars().all()
        ]

    await clear_game_state(game_uuid)
    await clear_lobby_ready(game_uuid)
    await unlock_all_participants(game_uuid)
    for rid in round_ids:
        await clear_buzzer(game_uuid, rid)

    await sio.emit("game_end", {"leaderboard": final_leaderboard}, room=f"game:{game_uuid}")


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

@sio.on("quiz_answer")
async def handle_quiz_answer(sid, data):
    """data: {round_id, location_id?, year_guess?}"""
    info = await get_sid_info(sid)
    if not info:
        return
    game_uuid = info["game_uuid"]
    participant_id = int(info["participant_id"])
    round_id = int(data.get("round_id", 0))
    location_id = data.get("location_id")
    year_guess = data.get("year_guess")

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(QuizResponse).where(
                QuizResponse.round_id == round_id, QuizResponse.participant_id == participant_id
            )
        )
        if existing.scalar_one_or_none():
            return  # already answered

        response = QuizResponse(
            round_id=round_id,
            participant_id=participant_id,
            selected_location_id=int(location_id) if location_id else None,
            year_guess=int(year_guess) if year_guess is not None else None,
        )
        db.add(response)
        await db.commit()


async def _close_quiz_after(game_uuid: str, round_id: int, delay: int):
    try:
        await asyncio.sleep(delay)
        await _finalize_quiz(game_uuid, round_id)
    except asyncio.CancelledError:
        pass


async def _finalize_quiz(game_uuid: str, round_id: int):
    logger.info("finalize_quiz game=%s round=%s", game_uuid, round_id)
    async with AsyncSessionLocal() as db:
        responses_result = await db.execute(
            select(QuizResponse)
            .options(selectinload(QuizResponse.selected_location), selectinload(QuizResponse.participant))
            .where(QuizResponse.round_id == round_id)
        )
        responses = responses_result.scalars().all()

        round_result = await db.execute(
            select(Round).options(selectinload(Round.locations)).where(Round.id == round_id)
        )
        r = round_result.scalar_one_or_none()
        if not r:
            return

        correct_location = next((loc for loc in r.locations if loc.is_correct), None)
        correct_location_name = correct_location.name if correct_location else None

        # Year scoring: closest guess wins (ties share the point); skipped if no target_year
        year_diffs: dict[int, int] = {}
        if r.target_year is not None:
            for resp in responses:
                if resp.year_guess is not None:
                    year_diffs[resp.participant_id] = abs(resp.year_guess - r.target_year)
        min_diff = min(year_diffs.values()) if year_diffs else None

        answered_ids: set[int] = set()
        results = []
        for resp in responses:
            answered_ids.add(resp.participant_id)
            location_pts = 1 if resp.selected_location and resp.selected_location.is_correct else 0
            year_pts = 1 if (min_diff is not None and year_diffs.get(resp.participant_id) == min_diff) else 0
            total = location_pts + year_pts

            resp.points_awarded = total
            resp.participant.score += total

            results.append({
                "participant_id": resp.participant_id,
                "username": resp.participant.username,
                "location_correct": bool(location_pts),
                "year_points": year_pts,
                "points_awarded": total,
                "score": resp.participant.score,
            })

        await db.commit()

        # Include participants who didn't submit an answer
        all_p_result = await db.execute(
            select(Participant).where(Participant.game_uuid == game_uuid)
        )
        for p in all_p_result.scalars().all():
            if p.id not in answered_ids:
                results.append({
                    "participant_id": p.id,
                    "username": p.username,
                    "location_correct": False,
                    "year_points": 0,
                    "points_awarded": 0,
                    "score": p.score,
                })

    leaderboard = sorted(results, key=lambda x: x["score"], reverse=True)
    await set_game_state(game_uuid, present_phase="revealed")
    await sio.emit(
        "quiz_result",
        {
            "results": results,
            "leaderboard": leaderboard,
            "round_id": r.id,
            "original_url": r.original_url,
            "ai_url": r.ai_url,
            "solution_text": r.solution_text,
            "target_year": r.target_year,
            "correct_location": correct_location_name,
        },
        room=f"game:{game_uuid}",
    )

    key = f"{game_uuid}:{round_id}"
    _quiz_tasks.pop(key, None)
