# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Halluzination** is a browser-based multiplayer party game. Players identify AI-manipulated photos. Three separate interfaces communicate in real time:

- **Handy-View** (`/play`) – Mobile buzzer, location tiles, year input
- **Präsentation** (`/present`) – 16:9 Beamer/TV display with blur→sharp effect, image slider, leaderboard
- **Admin Panel** (`/admin`) – Game Master control panel

## Repository Structure

```
halluzination/
├── docker-compose.yml
├── .env / .env.example
├── caddy/Caddyfile
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml        # dependencies managed via uv
│   ├── uv.lock               # always commit this
│   └── app/
│       ├── main.py           # FastAPI app entry point, socket.io mount
│       ├── models/           # SQLAlchemy ORM models
│       ├── routes/           # REST API endpoints
│       ├── socket/           # Socket.IO event handlers
│       └── services/         # business logic
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── lib/              # components, stores, socket client
│       └── routes/
│           ├── play/         # Handy-View
│           ├── present/      # Präsentation
│           └── admin/        # Admin Panel
└── db/
    └── migrations/           # SQL migrations (Alembic)
```

## Commands

**Full stack (Docker):**
```bash
cp .env.example .env
docker compose up --build
docker compose exec backend alembic upgrade head   # first run only
```

**Backend (local):**
```bash
cd backend
uv sync                                            # install from uv.lock
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                                      # run tests
```

**Frontend (local):**
```bash
cd frontend
npm install
npm run dev
npm run check   # svelte-check + tsc
npm run lint    # eslint
```

Local URLs: Frontend `http://localhost:5173` · Backend/Docs `http://localhost:8000/docs`

## Package Management

- **Backend:** always use `uv add <package>` – never `pip install` directly
- `pyproject.toml` and `uv.lock` must always be committed
- **Frontend:** `npm install <package>`

## Key Design Decisions

**Buzzer fairness:** Server assigns a timestamp on receipt. First event wins; all others are rejected via a Redis `SET NX EX` lock for the duration of the round.

**Admin auth:** All admin REST routes and admin Socket.IO events require the `X-Admin-Token` header. Token lives only in `.env`, never in the frontend bundle.

**Game state split:** Redis holds ephemeral live state (current round, buzzer lock, locked participants). PostgreSQL holds durable state (scores, responses, events).

**Reconnect:** Participants store `session_id` and `game_uuid` in `localStorage`. On reconnect the socket emits `rejoin` and the server restores their state.

**Blur effect:** Pure CSS `filter: blur()` transition triggered by `round_start` Socket.IO event. After 2 seconds the frontend enables the buzzer.

## Database Schema

| Table | Key fields |
|:---|:---|
| `games` | `uuid`, `title`, `status` |
| `participants` | `game_uuid`, `username`, `score` |
| `rounds` | `original_url`, `ai_url`, `solution_text`, `target_year`, `time_limit` |
| `locations` | `round_id`, `name`, `is_correct` (4 options per round) |
| `buzzer_events` | `round_id`, `participant_id`, `timestamp_ms`, `is_correct`, `points_awarded` |
| `quiz_responses` | `round_id`, `participant_id`, `location_id`, `year_guess`, `points_awarded` |

## Socket.IO Event Reference

**Server → Clients:**
- `round_start` `{ round_id, ai_image_url }` – triggers blur effect
- `buzzer_open` – buzzers become active
- `buzzer_locked` `{ winner_id, winner_name }` – all but winner disabled
- `quiz_start` `{ locations[], time_limit }` – show quiz on all handys
- `score_update` `{ leaderboard[] }` – update all displays
- `round_end` – reveal, show original vs. AI slider

**Client → Server:**
- `buzz` `{ participant_id, game_uuid, timestamp_ms }`
- `quiz_answer` `{ participant_id, location_id, year_guess }`
- `rejoin` `{ session_id, game_uuid }`

**Admin → Server** (all require `X-Admin-Token`):
- `judge` `{ round_id, participant_id, correct: bool }`
- `next_round`, `reveal`, `unlock_all`
- `unlock_participant` `{ participant_id }`

## Scoring

| Event | Points |
|:---|:---|
| Correct buzz | +2 |
| Correct location | +1 |
| Correct year (closest; ties share the point) | +1 |

## Admin Panel Keyboard Shortcuts

`R` Correct · `F` Lock/Wrong · `U` Unlock all · `V` Reveal · `Enter` Next round

## Conventions

- Code comments in **English**
- `.env` never in Git – only `.env.example`
