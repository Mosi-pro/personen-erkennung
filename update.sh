#!/usr/bin/env bash
# MOSI INTEL – Update: Sicherung, neuen Code holen, neu bauen, neu starten. Daten in ./data bleiben erhalten.
set -euo pipefail
cd "$(dirname "$0")"
./backup.sh
git pull --ff-only
docker compose build --pull
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
echo "Update abgeschlossen. Status:"; docker compose ps
