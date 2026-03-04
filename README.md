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

## Entwicklungsphasen

- **Phase 1** – Docker Setup, DB-Modelle, Auth, Upload, QR-Code, Beitreten
- **Phase 2** – WebSocket-Infrastruktur, Buzzer-Flow, Admin Panel, Präsentation
- **Phase 3** – Quiz (Location + Jahr), Punkteberechnung, Leaderboard
- **Phase 4** – Edge Cases, Sounds, Statistiken, Deployment, Härtung
