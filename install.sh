#!/usr/bin/env bash
# MOSI INTEL – Installation (Debian 13 / jedes Linux mit Docker Compose v2)
#   ./install.sh                 Basisinstallation (nur LAN-IP gebunden)
#   ./install.sh --searxng       zusätzlich eigenen SearXNG-Suchdienst starten
#   ./install.sh --port 8090     anderer Port
set -euo pipefail
cd "$(dirname "$0")"

WITH_SEARX=0; PORT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --searxng) WITH_SEARX=1 ;;
    --port) PORT="${2:?Port fehlt}"; shift ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
  esac; shift
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mFehler:\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || die "Docker ist nicht installiert. Debian: sudo apt install docker.io docker-compose-v2   (oder https://docs.docker.com/engine/install/debian/)"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 fehlt (apt install docker-compose-v2)."
docker info >/dev/null 2>&1 || die "Kein Zugriff auf den Docker-Daemon. Läuft er? Gehört dein Benutzer zur Gruppe 'docker' (oder mit sudo starten)?"

rand() { head -c 64 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c "$1"; }
setenv() { # setenv KEY VALUE  (ersetzt oder hängt an; ohne sed-Sonderzeichenprobleme)
  local tmp; tmp="$(mktemp)"
  grep -v "^$1=" .env > "$tmp" || true; printf '%s=%s\n' "$1" "$2" >> "$tmp"; cat "$tmp" > .env; rm -f "$tmp"
}

NEW=0
if [ ! -f .env ]; then
  say ".env wird aus .env.example erzeugt"
  cp .env.example .env; chmod 600 .env; NEW=1
  PASS="$(rand 20)"; setenv MOSI_ADMIN_PASSWORD "$PASS"; setenv SEARXNG_SECRET "$(rand 40)"
  IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' | head -n1 || true)"
  if [ -n "$IP" ]; then setenv MOSI_BIND "$IP"; else IP="127.0.0.1"; echo "Keine private LAN-IP gefunden – binde an 127.0.0.1 (in .env anpassbar)."; fi
fi
[ -n "$PORT" ] && setenv MOSI_PORT "$PORT"
if [ "$WITH_SEARX" = 1 ]; then setenv COMPOSE_PROFILES searxng; setenv SEARXNG_URL "http://searxng:8080"; fi

mkdir -p data backups
# Container läuft als UID 10001 – Datenverzeichnis passend berechtigen
chown 10001 data 2>/dev/null || sudo chown 10001 data 2>/dev/null || chmod 777 data
chmod 755 docker/searxng 2>/dev/null || true
chown -R 977:977 docker/searxng 2>/dev/null || sudo chown -R 977:977 docker/searxng 2>/dev/null || chmod -R a+rwX docker/searxng 2>/dev/null || true

say "Container werden gebaut (beim ersten Mal einige Minuten)…"
docker compose build
say "Anwendung wird gestartet…"
docker compose up -d

say "Warte auf Start…"
for i in $(seq 1 40); do
  st="$(docker inspect -f '{{.State.Health.Status}}' mosi-intel 2>/dev/null || echo starting)"
  [ "$st" = healthy ] && break; sleep 2
done
[ "$st" = healthy ] || { docker compose logs --tail=30 mosi; die "MOSI INTEL ist nicht gesund gestartet (siehe Log oben)."; }

# shellcheck disable=SC1091
set -a; . ./.env; set +a
echo
say "MOSI INTEL läuft:  http://${MOSI_BIND}:${MOSI_PORT}"
if [ "$NEW" = 1 ]; then
  echo "    Benutzer:  ${MOSI_ADMIN_USER}"
  echo "    Passwort:  ${MOSI_ADMIN_PASSWORD}   (steht in .env – nach dem Login unter Settings ändern)"
else
  echo "    Vorhandene .env wurde beibehalten (Login-Daten wie beim ersten Start)."
fi
[ -z "${SEARXNG_URL:-}${BRAVE_API_KEY:-}" ] && echo "    Hinweis: Noch kein Suchanbieter – in den Settings SearXNG/Brave eintragen oder ./install.sh --searxng ausführen."
exit 0
