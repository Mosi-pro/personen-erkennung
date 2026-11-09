import logging
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, security
from .routers import auth, images, reports, research, search, settings, system

log = logging.getLogger("mosi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def bootstrap_admin() -> None:
    if db.one("SELECT id FROM users LIMIT 1"):
        return
    pw = config.ADMIN_PASSWORD
    generated = not pw
    if generated:
        pw = secrets.token_urlsafe(12)
    db.run("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,strftime('%s','now'))", (config.ADMIN_USER, security.hash_password(pw)))
    if generated:
        log.warning("Initialer Benutzer '%s' mit generiertem Passwort: %s  (bitte nach dem Login ändern)", config.ADMIN_USER, pw)
    else:
        log.info("Initialer Benutzer '%s' angelegt.", config.ADMIN_USER)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    bootstrap_admin()
    for f in config.TMP_DIR.glob("*"):  # Reste abgebrochener Verarbeitungen entfernen
        f.unlink(missing_ok=True)
    yield


app = FastAPI(title="MOSI INTEL", version=config.VERSION, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def guard(request: Request, call_next):
    host = request.client.host if request.client else None
    if not config.ALLOW_PUBLIC and not security.client_is_private(host):
        return JSONResponse({"detail": "Zugriff nur aus dem lokalen Netzwerk erlaubt."}, status_code=403)
    if request.url.path.startswith("/api"):
        try:
            security.rate_limit(f"ip:{host}", 300, 60)
            if request.method not in security.SAFE_METHODS:
                origin = request.headers.get("origin")
                if origin and urlparse(origin).netloc != request.headers.get("host"):
                    raise HTTPException(403, "Ungültiger Origin.")
        except HTTPException as e:
            return JSONResponse({"detail": e.detail}, status_code=e.status_code, headers=e.headers)
    resp = await call_next(request)
    resp.headers.update({
        "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob: https: http:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'",
    })
    if request.url.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e["loc"] if x not in ("body", "query"))
        msgs.append(f"{loc}: {e['msg']}" if loc else e["msg"])
    return JSONResponse({"detail": "Ungültige Eingabe – " + "; ".join(msgs)}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unbehandelter Fehler: %s", request.url.path)
    return JSONResponse({"detail": "Interner Fehler. Details im Server-Log."}, status_code=500)


@app.get("/healthz", include_in_schema=False)
def healthz():
    db.one("SELECT 1")
    return {"status": "ok", "version": config.VERSION}


for r in (auth, settings, system, search, images, research, reports):
    app.include_router(r.router)

if config.STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Nicht gefunden.")
        f = (config.STATIC_DIR / path).resolve()
        if path and f.is_file() and config.STATIC_DIR in f.parents:  # Path-Traversal-Schutz
            return FileResponse(f)
        return FileResponse(config.STATIC_DIR / "index.html")
