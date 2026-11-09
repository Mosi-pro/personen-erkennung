"""Zentrale Konfiguration (ENV-Variablen)."""
import os
from pathlib import Path

VERSION = "1.0.0"


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


DATA_DIR = Path(os.getenv("MOSI_DATA_DIR", "./data")).resolve()
DB_PATH = DATA_DIR / "mosi.db"
IMAGE_DIR = DATA_DIR / "images"
TMP_DIR = DATA_DIR / "tmp"
STATIC_DIR = Path(os.getenv("MOSI_STATIC_DIR", str(Path(__file__).resolve().parent.parent / "static"))).resolve()

ADMIN_USER = os.getenv("MOSI_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("MOSI_ADMIN_PASSWORD", "")

MAX_UPLOAD_MB = int(os.getenv("MOSI_MAX_UPLOAD_MB", "10"))
SESSION_HOURS = int(os.getenv("MOSI_SESSION_HOURS", "12"))
COOKIE_SECURE = _bool("MOSI_COOKIE_SECURE", False)
# Standard: nur Zugriffe aus privaten Netzen (LAN / Loopback / Docker) erlaubt
ALLOW_PUBLIC = _bool("MOSI_ALLOW_PUBLIC", False)

# Standardwerte für Suchanbieter (können in den Einstellungen überschrieben werden)
DEFAULT_SEARXNG_URL = os.getenv("SEARXNG_URL", "")
DEFAULT_BRAVE_KEY = os.getenv("BRAVE_API_KEY", "")
