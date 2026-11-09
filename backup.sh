#!/usr/bin/env bash
# MOSI INTEL – Sicherung (konsistenter SQLite-Snapshot + gespeicherte Bilder) nach ./backups/
#   ./backup.sh            behält die letzten 14 Sicherungen (KEEP=30 ./backup.sh für andere Anzahl)
set -euo pipefail
cd "$(dirname "$0")"
KEEP="${KEEP:-14}"; TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p backups
docker inspect -f '{{.State.Running}}' mosi-intel 2>/dev/null | grep -q true || { echo "Container 'mosi-intel' läuft nicht – bitte zuerst starten (docker compose up -d)." >&2; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# Online-Snapshot der DB über die SQLite-Backup-API (im tmpfs des Containers) und per stdout herausstreamen
docker compose exec -T mosi python -c '
import sqlite3, sys, os
src = sqlite3.connect("/data/mosi.db"); dst = sqlite3.connect("/tmp/snap.db"); src.backup(dst); dst.close(); src.close()
sys.stdout.buffer.write(open("/tmp/snap.db", "rb").read()); os.remove("/tmp/snap.db")' > "$TMP/mosi.db"
[ -s "$TMP/mosi.db" ] || { echo "Datenbank-Snapshot fehlgeschlagen." >&2; exit 1; }
mkdir -p "$TMP/images"
docker compose exec -T mosi tar cf - -C /data images 2>/dev/null | tar xf - -C "$TMP" || true
tar czf "backups/mosi-$TS.tar.gz" -C "$TMP" .
chmod 600 "backups/mosi-$TS.tar.gz"
ls -1t backups/mosi-*.tar.gz | tail -n +$((KEEP+1)) | xargs -r rm -f
echo "Sicherung erstellt: backups/mosi-$TS.tar.gz ($(du -h "backups/mosi-$TS.tar.gz" | cut -f1))"
echo "Wiederherstellen: docker compose down && tar xzf backups/mosi-$TS.tar.gz -C data && chown -R 10001 data && docker compose up -d"
