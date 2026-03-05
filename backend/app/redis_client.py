import redis.asyncio as aioredis

from app.config import settings

redis = aioredis.from_url(settings.redis_url, decode_responses=True)


# --- Buzzer ---

async def try_lock_buzzer(game_uuid: str, round_id: int, participant_id: int) -> bool:
    """Atomically claim the buzzer. Returns True if this participant got it."""
    key = f"buzzer:{game_uuid}:{round_id}"
    result = await redis.set(key, participant_id, nx=True, ex=3600)
    return result is not None


async def get_buzzer(game_uuid: str, round_id: int) -> int | None:
    val = await redis.get(f"buzzer:{game_uuid}:{round_id}")
    return int(val) if val else None


async def clear_buzzer(game_uuid: str, round_id: int) -> None:
    await redis.delete(f"buzzer:{game_uuid}:{round_id}")


# --- Participant lock ---

async def lock_participant(game_uuid: str, participant_id: int) -> None:
    await redis.sadd(f"locked:{game_uuid}", participant_id)


async def unlock_participant(game_uuid: str, participant_id: int) -> None:
    await redis.srem(f"locked:{game_uuid}", participant_id)


async def unlock_all_participants(game_uuid: str) -> None:
    await redis.delete(f"locked:{game_uuid}")


async def is_locked(game_uuid: str, participant_id: int) -> bool:
    return bool(await redis.sismember(f"locked:{game_uuid}", participant_id))


# --- SID ↔ participant mapping ---

async def set_participant_sid(game_uuid: str, participant_id: int, sid: str) -> None:
    pipe = redis.pipeline()
    pipe.hset(f"p_sid:{game_uuid}:{participant_id}", "sid", sid)
    pipe.hset(f"sid_info:{sid}", mapping={"participant_id": str(participant_id), "game_uuid": game_uuid})
    pipe.expire(f"p_sid:{game_uuid}:{participant_id}", 86400)
    pipe.expire(f"sid_info:{sid}", 86400)
    await pipe.execute()


async def get_participant_sid(game_uuid: str, participant_id: int) -> str | None:
    return await redis.hget(f"p_sid:{game_uuid}:{participant_id}", "sid")


async def get_sid_info(sid: str) -> dict | None:
    info = await redis.hgetall(f"sid_info:{sid}")
    return info if info else None


async def remove_sid(sid: str) -> None:
    info = await get_sid_info(sid)
    if info:
        game_uuid = info.get("game_uuid")
        participant_id = info.get("participant_id")
        if game_uuid and participant_id:
            await redis.delete(f"p_sid:{game_uuid}:{participant_id}")
    await redis.delete(f"sid_info:{sid}")


# --- Lobby ready ---

async def mark_lobby_ready(game_uuid: str, participant_id: int) -> None:
    await redis.sadd(f"lobby_ready:{game_uuid}", participant_id)


async def get_lobby_ready_count(game_uuid: str) -> int:
    return int(await redis.scard(f"lobby_ready:{game_uuid}"))


async def clear_lobby_ready(game_uuid: str) -> None:
    await redis.delete(f"lobby_ready:{game_uuid}")


async def get_lobby_ready_set(game_uuid: str) -> set[int]:
    members = await redis.smembers(f"lobby_ready:{game_uuid}")
    return {int(m) for m in members}


# --- Game state ---

async def set_game_state(game_uuid: str, **kwargs) -> None:
    await redis.hset(f"game_state:{game_uuid}", mapping={k: str(v) for k, v in kwargs.items()})


async def get_game_state(game_uuid: str) -> dict:
    return await redis.hgetall(f"game_state:{game_uuid}")


async def get_game_state_field(game_uuid: str, field: str) -> str | None:
    return await redis.hget(f"game_state:{game_uuid}", field)


async def clear_game_state(game_uuid: str) -> None:
    await redis.delete(f"game_state:{game_uuid}")
