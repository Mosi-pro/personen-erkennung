import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, security

router = APIRouter(prefix="/api", tags=["research"], dependencies=[Depends(security.auth)])
CATEGORIES = ["Allgemein", "Beruflich", "Nachrichten", "Offiziell", "Veröffentlichung", "Organisation", "Pressemitteilung", "Bild", "Sonstiges"]


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field("", max_length=2000)


class ProjectPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    archived: bool | None = None


class ItemIn(BaseModel):
    type: Literal["web", "name", "image", "note"] = "web"
    title: str = Field(min_length=1, max_length=400)
    summary: str = Field("", max_length=3000)
    url: str = Field("", max_length=2000)
    source_domain: str = Field("", max_length=253)
    published: str | None = Field(None, max_length=40)
    retrieved_at: str = Field("", max_length=40)
    trust_level: Literal["high", "medium", "low", "unknown"] = "unknown"
    trust_score: int = Field(0, ge=0, le=100)
    match: Literal["", "confirmed", "name_only", "unconfirmed"] = ""
    category: str = Field("Allgemein", max_length=60)
    note: str = Field("", max_length=3000)
    data: dict = Field(default_factory=dict)


class ItemPatch(BaseModel):
    category: str | None = Field(None, max_length=60)
    note: str | None = Field(None, max_length=3000)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


def _project(pid: int) -> dict:
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Projekt nicht gefunden.")
    return p


def _touch(pid: int) -> None:
    db.run("UPDATE projects SET updated_at=? WHERE id=?", (time.time(), pid))


@router.get("/research")
def list_projects(archived: bool = False):
    return db.rows(
        "SELECT p.*, (SELECT COUNT(*) FROM items i WHERE i.project_id=p.id) AS item_count, "
        "(SELECT COUNT(*) FROM notes n WHERE n.project_id=p.id) AS note_count FROM projects p WHERE p.archived=? ORDER BY p.updated_at DESC",
        (1 if archived else 0,))


@router.post("/research", status_code=201)
def create_project(body: ProjectIn):
    now = time.time()
    pid = db.run("INSERT INTO projects(title,description,created_at,updated_at) VALUES(?,?,?,?)", (body.title.strip(), body.description.strip(), now, now))
    return _project(pid)


@router.get("/research/categories")
def categories():
    return CATEGORIES


@router.get("/research/{pid}")
def get_project(pid: int):
    p = _project(pid)
    items = db.rows("SELECT * FROM items WHERE project_id=? ORDER BY created_at DESC, id DESC", (pid,))
    for i in items:
        i["data"] = db.jload(i["data"], {})
    return {**p, "items": items, "notes": db.rows("SELECT * FROM notes WHERE project_id=? ORDER BY created_at DESC, id DESC", (pid,))}


@router.patch("/research/{pid}")
def patch_project(pid: int, body: ProjectPatch):
    _project(pid)
    if body.title is not None:
        db.run("UPDATE projects SET title=? WHERE id=?", (body.title.strip(), pid))
    if body.description is not None:
        db.run("UPDATE projects SET description=? WHERE id=?", (body.description.strip(), pid))
    if body.archived is not None:
        db.run("UPDATE projects SET archived=? WHERE id=?", (1 if body.archived else 0, pid))
    _touch(pid)
    return _project(pid)


@router.delete("/research/{pid}")
def delete_project(pid: int):
    _project(pid)
    db.run("DELETE FROM projects WHERE id=?", (pid,))
    return {"ok": True}


@router.post("/research/{pid}/items", status_code=201)
def add_item(pid: int, body: ItemIn):
    _project(pid)
    if body.url and not body.url.startswith(("http://", "https://")):
        raise HTTPException(422, "Ungültige URL (nur http/https).")
    if body.url and db.one("SELECT id FROM items WHERE project_id=? AND url=?", (pid, body.url)):
        raise HTTPException(409, "Diese Quelle ist im Projekt bereits gespeichert.")
    iid = db.run(
        "INSERT INTO items(project_id,type,title,summary,url,source_domain,published,retrieved_at,trust_level,trust_score,match,category,note,data,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, body.type, body.title, body.summary, body.url, body.source_domain, body.published, body.retrieved_at or time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
         body.trust_level, body.trust_score, body.match, body.category or "Allgemein", body.note, json.dumps(body.data, ensure_ascii=False), time.time()))
    _touch(pid)
    return db.one("SELECT * FROM items WHERE id=?", (iid,))


@router.patch("/research/{pid}/items/{iid}")
def patch_item(pid: int, iid: int, body: ItemPatch):
    if not db.one("SELECT id FROM items WHERE id=? AND project_id=?", (iid, pid)):
        raise HTTPException(404, "Ergebnis nicht gefunden.")
    if body.category is not None:
        db.run("UPDATE items SET category=? WHERE id=?", (body.category.strip() or "Allgemein", iid))
    if body.note is not None:
        db.run("UPDATE items SET note=? WHERE id=?", (body.note, iid))
    _touch(pid)
    return db.one("SELECT * FROM items WHERE id=?", (iid,))


@router.delete("/research/{pid}/items/{iid}")
def delete_item(pid: int, iid: int):
    if not db.one("SELECT id FROM items WHERE id=? AND project_id=?", (iid, pid)):
        raise HTTPException(404, "Ergebnis nicht gefunden.")
    db.run("DELETE FROM items WHERE id=?", (iid,))
    _touch(pid)
    return {"ok": True}


@router.post("/research/{pid}/notes", status_code=201)
def add_note(pid: int, body: NoteIn):
    _project(pid)
    nid = db.run("INSERT INTO notes(project_id,text,created_at) VALUES(?,?,?)", (pid, body.text.strip(), time.time()))
    _touch(pid)
    return db.one("SELECT * FROM notes WHERE id=?", (nid,))


@router.delete("/research/{pid}/notes/{nid}")
def delete_note(pid: int, nid: int):
    if not db.one("SELECT id FROM notes WHERE id=? AND project_id=?", (nid, pid)):
        raise HTTPException(404, "Notiz nicht gefunden.")
    db.run("DELETE FROM notes WHERE id=?", (nid,))
    _touch(pid)
    return {"ok": True}


# ---------- Suchverlauf ----------
@router.get("/searches")
def searches(limit: int = 20):
    return db.rows("SELECT id,kind,label,result_count,created_at FROM searches ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),))


@router.get("/searches/{sid}")
def get_search(sid: int):
    r = db.one("SELECT * FROM searches WHERE id=?", (sid,))
    if not r:
        raise HTTPException(404, "Suche nicht gefunden.")
    payload = db.jload(r["payload"], {})
    if r["kind"] == "image":
        a = payload.get("analysis", {})
        a.pop("signature", None)
        payload = {"analysis": a}
    return {"id": r["id"], "kind": r["kind"], "label": r["label"], "created_at": r["created_at"], **payload}


@router.delete("/searches/{sid}")
def delete_search(sid: int):
    db.run("DELETE FROM searches WHERE id=?", (sid,))
    return {"ok": True}


# ---------- Dashboard / globale Suche ----------
@router.get("/dashboard")
def dashboard():
    week = time.time() - 7 * 86400
    by_kind = {r["kind"]: r["n"] for r in db.rows("SELECT kind, COUNT(*) n FROM searches WHERE created_at>? GROUP BY kind", (week,))}
    return {
        "stats": {
            "projects": db.one("SELECT COUNT(*) n FROM projects WHERE archived=0")["n"],
            "archived": db.one("SELECT COUNT(*) n FROM projects WHERE archived=1")["n"],
            "sources": db.one("SELECT COUNT(*) n FROM items")["n"],
            "searches_week": by_kind, "searches_total": db.one("SELECT COUNT(*) n FROM searches")["n"],
        },
        "recent_projects": db.rows("SELECT p.id,p.title,p.updated_at,(SELECT COUNT(*) FROM items i WHERE i.project_id=p.id) AS item_count FROM projects p WHERE archived=0 ORDER BY updated_at DESC LIMIT 5"),
        "recent_searches": db.rows("SELECT id,kind,label,result_count,created_at FROM searches ORDER BY id DESC LIMIT 6"),
        "recent_sources": db.rows("SELECT i.id,i.title,i.url,i.source_domain,i.trust_level,i.retrieved_at,i.project_id,p.title AS project FROM items i JOIN projects p ON p.id=i.project_id WHERE i.url!='' ORDER BY i.created_at DESC LIMIT 8"),
    }


@router.get("/local-search")
def local_search(q: str):
    q = q.strip()[:100]
    if len(q) < 2:
        return {"projects": [], "items": [], "searches": []}
    like = f"%{q.replace('%', '').replace('_', '')}%"
    return {
        "projects": db.rows("SELECT id,title FROM projects WHERE title LIKE ? OR description LIKE ? LIMIT 5", (like, like)),
        "items": db.rows("SELECT i.id,i.title,i.project_id,i.source_domain FROM items i WHERE i.title LIKE ? OR i.summary LIKE ? OR i.note LIKE ? LIMIT 8", (like, like, like)),
        "searches": db.rows("SELECT id,kind,label FROM searches WHERE label LIKE ? ORDER BY id DESC LIMIT 5", (like,)),
    }
