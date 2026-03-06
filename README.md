# Halluzination

Ein browserbasiertes Multiplayer-Party-Game, bei dem Spieler KI-veränderte Fotos entlarven müssen – ganz ohne App-Installation.

## Das Konzept

Genau wie eine KI Dinge erfindet, die nicht existieren, zeigt dieses Spiel Bilder, die subtil durch KI verfremdet wurden. Ein Bildschirm (TV/Beamer) zeigt das Spielgeschehen für alle, jeder Teilnehmer spielt auf seinem eigenen Smartphone. Ein Game Master moderiert das Ganze vom Laptop aus.

**Ablauf einer Runde:**

1. Das veränderte Bild erscheint zunächst unscharf – nach 2 Sekunden wird es scharf und die Buzzer werden aktiv
2. Wer die Veränderung zuerst erkennt, drückt den Buzzer
3. Der Game Master bewertet die Antwort (+2 Punkte bei Richtig)
4. Danach erscheint auf allen Handys gleichzeitig eine Zusatzfrage: Wo wurde das Foto aufgenommen? (4 Optionen) und in welchem Jahr? (je +1 Punkt)
5. Das animierte Leaderboard zeigt nach jeder Runde den aktuellen Punktestand

## Die drei Interfaces

| Interface | Zielgerät | Beschreibung |
|:---|:---|:---|
| **Handy-View** | Smartphone | Buzzer, Location-Kacheln, Jahreseingabe – Mobile First, seniorengerecht |
| **Präsentation** | TV / Beamer | Blur-Effekt, Image-Comparison-Slider, Leaderboard-Diagramm |
| **Admin Panel** | Laptop | Spielsteuerung, Teilnehmer-Kacheln, Tastatur-Shortcuts, Drag & Drop Runden |

## Tech Stack

| Schicht | Technologie |
|:---|:---|
| Backend | FastAPI + python-socketio |
| Datenbank | PostgreSQL 16 |
| Cache / State | Redis 7 |
| Frontend | SvelteKit |
| Reverse Proxy | Caddy 2 (automatisches HTTPS) |
| Hosting | Docker Compose auf Debian-Server |

## Datenbank lokal aufsetzen

Docker muss installiert sein.

```bash
# PostgreSQL starten
make db-up

# Schema anlegen
make db-upgrade

# Schema zurücksetzen
make db-reset

# Neue Migration nach Modelländerung
make db-migrate msg="beschreibung der änderung"

# Direkter DB-Zugriff
docker compose exec db psql -U halluzination -d halluzination
```

## Produktion aufsetzen (Docker Compose)

Diese Anleitung nutzt [`docker-compose.prod.yml`](docker-compose.prod.yml) und die veröffentlichten Images aus `ghcr.io/friedjof/halluzination/*:latest`.

### 1. Voraussetzungen

- Linux-Server mit Docker + Docker Compose Plugin
- Domain, die auf den Server zeigt (A/AAAA-Record)
- Ports `80` und `443` offen (für HTTPS via Caddy/Let's Encrypt)

### 2. Projekt holen

```bash
git clone git@github.com:Friedjof/Halluzination.git
cd Halluzination
```

### 3. Produktive `.env` erstellen

```bash
cp .env.example .env
```

Für `docker-compose.prod.yml` sind diese Variablen zwingend:

```env
ADMIN_TOKEN=<starkes-geheimes-token>
POSTGRES_USER=halluzination
POSTGRES_PASSWORD=<starkes-db-passwort>
POSTGRES_DB=halluzination
APP_DOMAIN=deine-domain.tld
```

Hinweise:

- `APP_DOMAIN` wird in der Prod-Compose für Caddy-Host, Backend-CORS/Join-URLs und Frontend-Origin verwendet.
- `DATABASE_URL`, `REDIS_URL`, `ALLOWED_ORIGINS`, `FRONTEND_URL` und `UPLOAD_DIR` sind in Prod nicht zwingend, da sie per `docker-compose.prod.yml` gesetzt werden.

### 4. Container starten (Erstdeployment)

```bash
# Aktuelle Images holen
docker compose -f docker-compose.prod.yml pull

# Datenbank/Redis hochfahren
docker compose -f docker-compose.prod.yml up -d db redis

# Migrationen anwenden
docker compose -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head

# Gesamten Stack starten
docker compose -f docker-compose.prod.yml up -d
```

### 5. Status prüfen

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend caddy
```

Dann im Browser öffnen: `https://deine-domain.tld/admin`

### 6. Update auf neue Releases

```bash
git pull
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

Hinweise:

- Backend- und Frontend-Image sind auf `latest` fixiert.
- Uploads bleiben persistent im Docker-Volume `uploads_data` erhalten.
- Postgres und Redis laufen nur intern im Docker-Netz (`data_net`) und sind nicht nach außen veröffentlicht.

## Entwicklungsphasen

- **Phase 1** – Docker Setup, DB-Modelle, Auth, Upload, QR-Code, Beitreten
- **Phase 2** – WebSocket-Infrastruktur, Buzzer-Flow, Admin Panel, Präsentation
- **Phase 3** – Quiz (Location + Jahr), Punkteberechnung, Leaderboard
- **Phase 4** – Edge Cases, Sounds, Statistiken, Deployment, Härtung
