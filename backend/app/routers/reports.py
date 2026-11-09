from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from .. import db, security
from ..services import reports

router = APIRouter(prefix="/api/reports", tags=["reports"])
TYPES = {"pdf": "application/pdf", "html": "text/html; charset=utf-8", "json": "application/json"}


class ExportIn(BaseModel):
    project_id: int
    format: Literal["pdf", "html", "json"]


@router.post("/export")
def export(body: ExportIn, user=Depends(security.auth)):
    security.limit_user(user, "export", 20)
    p = db.one("SELECT * FROM projects WHERE id=?", (body.project_id,))
    if not p:
        raise HTTPException(404, "Projekt nicht gefunden.")
    items = db.rows("SELECT * FROM items WHERE project_id=? ORDER BY category, created_at", (p["id"],))
    notes = db.rows("SELECT * FROM notes WHERE project_id=? ORDER BY created_at", (p["id"],))
    rep = reports.build(p, items, notes)
    data = {"pdf": reports.to_pdf, "html": reports.to_html, "json": reports.to_json}[body.format](rep)
    fn = reports.filename(p["title"], body.format)
    return Response(data, media_type=TYPES[body.format], headers={"Content-Disposition": f'attachment; filename="{fn}"', "Cache-Control": "no-store"})
