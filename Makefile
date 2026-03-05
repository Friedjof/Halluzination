.PHONY: dev backend-dev frontend-dev backend frontend \
        db-up db-wait db-upgrade db-migrate db-reset frontend-install check-env

# ---------------------------------------------------------------------------
# Dev – alles auf einmal
# ---------------------------------------------------------------------------

dev: check-env db-up db-wait db-upgrade frontend-install
	@echo ""
	@echo "  Backend  →  http://localhost:8000/docs"
	@echo "  Frontend →  http://localhost:5173/admin"
	@echo ""
	@trap 'kill 0' INT; \
	  (cd backend  && uv run uvicorn app.main:app --reload --port 8000) & \
	  (cd frontend && npm run dev) & \
	  wait

# ---------------------------------------------------------------------------
# Dev-Server (einzeln)
# ---------------------------------------------------------------------------

backend-dev:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Docker-Images bauen
# ---------------------------------------------------------------------------

backend:
	docker build -t halluzination-backend ./backend

frontend:
	docker build -t halluzination-frontend ./frontend

# ---------------------------------------------------------------------------
# Datenbank
# ---------------------------------------------------------------------------

db-up:
	docker compose up db redis -d

# Wartet bis Postgres Verbindungen akzeptiert (max. 30 Sekunden).
# -T: kein pseudo-TTY (wichtig im nicht-interaktiven Makefile-Kontext)
db-wait:
	@echo "Warte auf Datenbank..."
	@for i in $$(seq 1 30); do \
	  docker compose exec -T db pg_isready -q 2>/dev/null && echo "  DB bereit." && exit 0; \
	  sleep 1; \
	done; echo "Fehler: Datenbank nicht erreichbar nach 30 Sekunden." >&2; exit 1

db-upgrade:
	cd backend && uv run alembic upgrade head

db-migrate:
	@test -n "$(msg)" || (echo "Benutzung: make db-migrate msg=\"beschreibung\"" && exit 1)
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

db-reset:
	cd backend && uv run alembic downgrade base && uv run alembic upgrade head

# ---------------------------------------------------------------------------
# Hilfsziele
# ---------------------------------------------------------------------------

frontend-install:
	cd frontend && [ -d node_modules ] || npm install

check-env:
	@test -f .env || (echo "" && echo "Fehler: .env nicht gefunden." && echo "Bitte zuerst ausführen: cp .env.example .env" && echo "" && exit 1)
