# MOSI INTEL

Selbst gehostete OSINT-Rechercheplattform für öffentlich zugängliche Informationen: **Name Research** (wo taucht ein Name öffentlich auf – z. B. dein eigener), **Web Intelligence**, **Image Research**, Rechercheverwaltung und PDF/HTML/JSON-Berichte. Läuft als **ein** Docker-Container (FastAPI + SQLite + React), optional mit SearXNG.

## Was MOSI INTEL tut – und was bewusst nicht

| Modul | Funktion |
|---|---|
| **Name Research** | Fragt Suchanbieter (SearXNG / Brave) und die Wikipedia-API ab. Ergebnisse gegliedert in Beruflicher Hintergrund, Tätigkeiten, Organisationen, Veröffentlichungen, Nachrichten, Pressemitteilungen, offizielle Webseiten. Jeder Treffer: Titel, Textauszug, Originalquelle, Veröffentlichungs- und Abrufdatum, Vertrauensbewertung. Tab **„Wo taucht dein Name auf?"** listet Fundstellen nach Domain. |
| **Web Intelligence** | Freie Suche mit mehreren Anfragen, Zeitraum-/Domainfilter, Nachrichtenmodus, Duplikaterkennung, Quellenkarten, Speichern. |
| **Image Research** | Upload (Drag & Drop, Format-/Größenprüfung) → lokale Analyse: Text im Bild (Tesseract-OCR), QR-Codes, Farben, EXIF (optional), GPS→Ort (optional) → daraus Suchbegriffe (editierbar) → Bild- und Webtreffer; Bildtreffer werden lokal per Hash/Farbhistogramm nach visueller Ähnlichkeit sortiert. Bilder werden **nur im Arbeitsspeicher** verarbeitet und nicht gespeichert, außer du wählst es aus. |
| **Saved Researches / Reports** | Projekte, Notizen, Kategorien, Archiv, Löschen; Export als PDF, HTML, JSON mit Quellen und Hinweisen zur Datenqualität. |

**Bewusste Grenzen (Datenschutz):**
- **Keine Gesichtserkennung**, keine biometrischen Vorlagen, keine Suche „alle Bilder dieser Person anhand ihres Gesichts". Ein einfacher Gesichts-Detektor dient nur als Schutzschalter: Zeigt ein Bild Personen, wird es nicht für eine Websuche verwendet.
- Name Research verlangt Angabe des Zwecks (**eigener Name / öffentlich auftretende Person / Organisation**) und eine Bestätigung. Eingaben wie E-Mail, Telefonnummer, URL werden abgelehnt. E-Mail-Adressen und Telefonnummern in Textauszügen werden entfernt. Personensuch-/Datenbroker-Seiten werden bei Recherchen zu Dritten ausgeblendet; bei der **Selbstauskunft** werden sie angezeigt und markiert (damit du Löschung verlangen kannst).
- Namensvetter: Treffer müssen alle Namensbestandteile enthalten. Mit Kontext/Organisation/Region werden Treffer als „bestätigt" oder „unbestätigt (evtl. Namensvetter)" getrennt; Wikipedia-Namensvetter werden aufgelistet. Es wird nichts ohne Beleg zugeordnet.
- Es werden nur Suchtreffer-Auszüge verarbeitet; Seiten werden nicht gecrawlt. Zusammenfassungen sind mechanisch aus Auszügen zusammengestellt (kein KI-Modell) und mit Quellennummern belegt.
- Die **Vertrauensbewertung** ist eine Domain-Heuristik (Behörde/Hochschule, etablierte Medien, Nachschlagewerke > berufliche Profile > Sonstige > nutzergenerierte Inhalte/Datenbroker) und ersetzt keine inhaltliche Prüfung.

## Installation (Debian 13 / Docker)

Voraussetzung: `sudo apt install docker.io docker-compose-v2 git`

```bash
git clone <dieses-repository> mosi-intel && cd mosi-intel
./install.sh --searxng        # --searxng = kostenlosen eigenen Suchdienst gleich mitstarten
```

`install.sh` erzeugt `.env` (zufälliges Passwort, LAN-IP als Bind-Adresse), baut das Image, startet die Anwendung, wartet auf den Healthcheck und gibt **URL, Benutzer und Passwort** aus. Anderer Port: `./install.sh --port 8090` oder `MOSI_PORT` in `.env`.

Ohne `--searxng`: unter **Settings** eine SearXNG-URL oder einen Brave-API-Schlüssel eintragen (oder in `.env`), dort per „Verbindung testen" prüfen. Ohne Suchanbieter zeigt MOSI INTEL eine klare Fehlermeldung – es werden **nie** Ergebnisse simuliert.

### Zugriff über das lokale Netzwerk
1. `install.sh` bindet den Port automatisch an die private LAN-IP des Servers (`MOSI_BIND` in `.env`). Prüfen: `hostname -I`.
2. Im Browser eines Geräts im selben Netz: `http://<LAN-IP>:<PORT>` (Standard-Port 8080), z. B. `http://192.168.1.50:8080`. Funktioniert auf Desktop, Tablet und Smartphone.
3. Standardmäßig ist **nichts** ins Internet exponiert: Bind auf LAN-IP + die App weist Anfragen von öffentlichen IP-Adressen ab (`MOSI_ALLOW_PUBLIC=false`). **Keine Port-Weiterleitung im Router einrichten.** Für Fernzugriff ein VPN (WireGuard/Tailscale) verwenden; hinter HTTPS-Proxy `MOSI_COOKIE_SECURE=true` setzen.
4. Firewall (optional): `sudo ufw allow from 192.168.1.0/24 to any port 8080 proto tcp`

### Betrieb
```bash
./update.sh                   # Backup → git pull → neu bauen → neu starten (Daten bleiben)
./backup.sh                   # Snapshot nach ./backups/ (DB + gespeicherte Bilder), behält 14 Stück
docker compose logs -f mosi   # Logs
docker compose restart mosi   # Neustart; Daten liegen in ./data
```
Wiederherstellen: `docker compose down && tar xzf backups/<datei>.tar.gz -C data && chown -R 10001 data && docker compose up -d`

## Kostenlose Suchanbieter
| Anbieter | Kosten | Einrichtung |
|---|---|---|
| **SearXNG** (empfohlen) | kostenlos, selbst gehostet | `./install.sh --searxng` (JSON-API ist in `docker/searxng/settings.yml` aktiviert) |
| **Brave Search API** | kostenloses Kontingent, Schlüssel nötig | Settings → API-Schlüssel (nur serverseitig gespeichert, nie im Frontend sichtbar) |
| **Wikipedia-API** | kostenlos, immer aktiv | – (liefert Hintergrund und Namensvetter) |

Es werden ausschließlich dokumentierte APIs verwendet – kein Scraping von Suchmaschinen. Weitere Anbieter: Adapter in `backend/app/providers.py` (`SearchService`).
**Wichtig:** SearXNG greift selbst auf öffentliche Suchmaschinen zu; deren Verfügbarkeit/Limits liegen außerhalb von MOSI INTEL.

## Ressourcen
Gemessen (Container mit denselben Laufzeitflags wie in `docker-compose.yml`, Python 3.13, ohne SearXNG):

| | Wert |
|---|---|
| RAM im Leerlauf | ca. **70 MB** |
| RAM nach Bildanalyse (OpenCV geladen) + PDF-Export | ca. **80–170 MB** (Spitze je nach Bildgröße; Limit im Compose: 768 MB) |
| CPU im Leerlauf | ein Prozess, ein Worker, keine Hintergrundjobs/Timer – nur bei Anfragen |
| Image-Größe | nicht in dieser Umgebung gemessen; Erwartung ca. 450–550 MB mit OCR, ca. 350–450 MB mit `INSTALL_OCR=0` (`docker images mosi-intel` zeigt den realen Wert) |
| SearXNG (optional) | zusätzlich ca. 150–300 MB RAM, ca. 300 MB Image |
| Nutzerdaten | SQLite-Datei, wenige KB pro gespeicherter Quelle |

Keine lokalen KI-Modelle. Gesamt ohne SearXNG also deutlich unter 512 MB RAM.

## Sicherheit
Login mit scrypt-Passwort-Hash · serverseitige Sessions (HttpOnly, SameSite=Strict-Cookie) · CSRF-Token + Origin-Prüfung bei schreibenden Anfragen · Rate-Limiting (global, Login mit Kontosperre nach 8 Fehlversuchen, pro Funktion) · Upload-Limit, Format-/Inhaltsprüfung über Pillow, Pixel-Limit, serverseitig erzeugte Dateinamen (kein Path Traversal), SPA-Auslieferung mit Traversal-Schutz · SSRF-Schutz beim Laden von Vorschaubildern · Datenbank liegt in `./data`, wird nie über HTTP ausgeliefert, Dateirechte 600 · Container: Nicht-Root, read-only Dateisystem, keine Capabilities, `no-new-privileges` · API-Schlüssel nur im Backend · CSP/Security-Header.
Hinweis: Vorschaubilder der Suchergebnisse lädt der Browser direkt von den Fremdseiten (ohne Referrer). Wer das nicht möchte, nutzt keine Bildsuche.

## Verwendete Dienste und Software
Python 3.13, FastAPI, Pydantic, httpx, Pillow, OpenCV (headless), NumPy, fpdf2 · React, TypeScript, Vite, Tailwind CSS, Lucide, Inter (lokal ausgeliefert) · SQLite · Docker/Compose · optional Tesseract-OCR, SearXNG · externe APIs nur auf Wunsch: Brave Search, Wikipedia, OpenStreetMap Nominatim (GPS→Ort, standardmäßig aus).

## Projektstruktur
```
Dockerfile  docker-compose.yml  .env.example  install.sh  update.sh  backup.sh
docker/searxng/settings.yml
backend/app/   main.py config.py db.py security.py providers.py
               routers/   auth settings system search images research reports
               services/  name_research.py image_research.py reports.py
backend/tests/test_app.py        (23 Tests)
frontend/src/  App.tsx api.ts  components/  pages/ (Dashboard, ImageResearch, NameResearch, WebIntelligence→WebIntel, Saved, Reports, Settings)
```

## API (alle unter `/api`, Session-Cookie + `X-CSRF-Token` erforderlich)
`POST /auth/login|logout|password` · `GET /auth/me` · `POST /web-search` · `POST /name-research` · `POST /image-research` · `POST /image-research/{id}/search` · `GET|POST /research` · `GET|PATCH|DELETE /research/{id}` · `POST /research/{id}/items|notes` · `PATCH|DELETE /research/{id}/items/{iid}` · `POST /reports/export` · `GET /system/status` · `GET|PUT /settings` · `POST /settings/test/{anbieter}` · `GET /dashboard` · `GET /local-search` · `GET /searches[/{id}]`. Health: `GET /healthz`.

## Entwicklung & Tests
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt pytest
python -m pytest -q tests                      # 23 Tests (Login, CSRF, Suche, Namensrecherche, Upload, Projekte, PDF …)
MOSI_DATA_DIR=./data MOSI_ADMIN_PASSWORD=dev uvicorn app.main:app --reload
cd ../frontend && npm ci && npm run dev        # Vite-Proxy auf :8000
```

## Bekannte Grenzen
- Die „Erkennung" von Bildinhalten beschränkt sich bewusst auf leichte Verfahren (OCR, QR, Farben, EXIF/GPS). Objekte/Logos ohne Text werden nicht klassifiziert (dafür wären neuronale Modelle nötig). Ohne lesbaren Text gibst du Suchbegriffe manuell ein.
- Echte Rückwärts-Bildsuche (Upload an Google/TinEye) gibt es ohne kostenpflichtige APIs nicht; MOSI INTEL sucht über abgeleitete Begriffe.
- PDF nutzt Standard-Schriften (Latin-1); Zeichen außerhalb (z. B. Kyrillisch) werden als `?` ausgegeben. HTML/JSON enthalten alles.
