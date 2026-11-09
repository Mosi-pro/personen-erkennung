"""Passwort-Hashing, Sessions, CSRF, Rate-Limiting, LAN-Prüfung."""
import hashlib
import hmac
import ipaddress
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config, db

COOKIE = "mosi_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


# ---------- Passwörter (scrypt, stdlib) ----------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    h = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


# ---------- Sessions ----------
def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    db.run(
        "INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)",
        (_th(token), user_id, csrf, time.time() + config.SESSION_HOURS * 3600),
    )
    db.run("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
    return token, csrf


def destroy_session(token: str) -> None:
    db.run("DELETE FROM sessions WHERE token_hash=?", (_th(token),))


def destroy_user_sessions(user_id: int) -> None:
    db.run("DELETE FROM sessions WHERE user_id=?", (user_id,))


def auth(request: Request) -> dict:
    """FastAPI-Dependency: gültige Session + CSRF-Token bei schreibenden Methoden."""
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Nicht angemeldet.")
    s = db.one(
        "SELECT s.csrf, s.expires_at, u.id, u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
        (_th(token),),
    )
    if not s or s["expires_at"] < time.time():
        raise HTTPException(401, "Sitzung abgelaufen. Bitte neu anmelden.")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent, s["csrf"]):
            raise HTTPException(403, "CSRF-Prüfung fehlgeschlagen.")
    return {"id": s["id"], "username": s["username"], "csrf": s["csrf"]}


# ---------- Rate Limiting (In-Memory, gleitendes Fenster) ----------
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()
_last_gc = 0.0


def rate_limit(key: str, max_hits: int, window: int) -> None:
    global _last_gc
    now = time.time()
    with _lock:
        if now - _last_gc > 300:
            for k in [k for k, d in _hits.items() if not d or now - d[-1] > 3600]:
                del _hits[k]
            _last_gc = now
        d = _hits[key]
        while d and now - d[0] > window:
            d.popleft()
        if len(d) >= max_hits:
            raise HTTPException(429, "Zu viele Anfragen. Bitte kurz warten.", headers={"Retry-After": str(window)})
        d.append(now)


def limit_user(user: dict, bucket: str, max_hits: int = 20, window: int = 60) -> None:
    rate_limit(f"{bucket}:{user['id']}", max_hits, window)


# ---------- Login-Sperre ----------
_fail: dict[str, list[float]] = defaultdict(list)


def login_locked(username: str) -> bool:
    now = time.time()
    with _lock:
        _fail[username] = [t for t in _fail[username] if now - t < 900]
        return len(_fail[username]) >= 8


def login_failed(username: str) -> None:
    with _lock:
        _fail[username].append(time.time())


def login_ok(username: str) -> None:
    with _lock:
        _fail.pop(username, None)


# ---------- LAN-Prüfung ----------
def client_is_private(host: str | None) -> bool:
    if not host:
        return False
    if host == "testclient":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local
