"""SQLite-Zugriff (stdlib). Eine Verbindung pro Aufruf, WAL-Modus."""
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type TEXT NOT NULL DEFAULT 'web',
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  source_domain TEXT NOT NULL DEFAULT '',
  published TEXT,
  retrieved_at TEXT NOT NULL,
  trust_level TEXT NOT NULL DEFAULT 'unknown',
  trust_score INTEGER NOT NULL DEFAULT 0,
  match TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'Allgemein',
  note TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_project ON items(project_id);
CREATE TABLE IF NOT EXISTS notes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS searches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  params TEXT NOT NULL DEFAULT '{}',
  payload TEXT NOT NULL DEFAULT '{}',
  result_count INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
"""


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    with tx() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
    try:
        config.DB_PATH.chmod(0o600)
    except OSError:
        pass


def rows(sql: str, args: tuple | list = ()) -> list[dict]:
    with tx() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(sql: str, args: tuple | list = ()) -> dict | None:
    r = rows(sql, args)
    return r[0] if r else None


def run(sql: str, args: tuple | list = ()) -> int:
    with tx() as c:
        return c.execute(sql, args).lastrowid or 0


def get_settings() -> dict[str, str]:
    return {r["key"]: r["value"] for r in rows("SELECT key,value FROM settings")}


def set_setting(key: str, value: str) -> None:
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def log_search(kind: str, label: str, params: dict, payload: dict, count: int) -> int:
    return run(
        "INSERT INTO searches(kind,label,params,payload,result_count,created_at) VALUES(?,?,?,?,?,?)",
        (kind, label[:200], json.dumps(params, ensure_ascii=False), json.dumps(payload, ensure_ascii=False, default=str), count, time.time()),
    )


def jload(s: str | None, default: Any = None) -> Any:
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default
