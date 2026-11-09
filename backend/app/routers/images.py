from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .. import config, db, providers as P, security
from ..services import image_research as IR

router = APIRouter(prefix="/api/image-research", tags=["image"])


@router.post("")
async def image_research(file: UploadFile = File(...), include_exif: bool = Form(False), save_image: bool = Form(False),
                         user=Depends(security.auth)):
    security.limit_user(user, "image", 10)
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 256):
        data += chunk
        if len(data) > limit:
            raise HTTPException(413, f"Datei zu groß (max. {config.MAX_UPLOAD_MB} MB).")
    data = bytes(data)
    svc = P.SearchService(db.get_settings())
    try:
        analysis = IR.analyze(data, include_exif, svc)
    except IR.ImageError as e:
        raise HTTPException(422, str(e))
    stored = None
    if save_image:
        ext = IR.FORMATS[IR.validate(data)[1].format]
        stored = IR.store_image(data, ext)
    # Standard: Bild wird nur im Arbeitsspeicher verarbeitet und nach der Antwort verworfen.
    analysis["image_saved"] = bool(stored)
    sid = db.log_search("image", f"Bild {analysis['width']}×{analysis['height']} {analysis['format']}", {"include_exif": include_exif, "saved": stored},
                        {"analysis": analysis, "stored": stored}, 0)
    out = {"id": sid, "analysis": {k: v for k, v in analysis.items() if k != "signature"}, "search": None}
    if analysis["contains_people"]:
        return out
    if analysis["terms"] and svc.configured():
        try:
            res = IR.search(svc, analysis["terms"], analysis["signature"])
            out["search"] = res
        except IR.ImageError:
            pass
    elif analysis["terms"]:
        out["search"] = {"terms": analysis["terms"], "images": [], "pages": [], "errors": ["Kein Suchanbieter konfiguriert (SearXNG oder Brave in den Settings eintragen)."]}
    return out


class _Terms(__import__("pydantic").BaseModel):
    terms: list[str]


@router.post("/{sid}/search")
def research_again(sid: int, body: _Terms, user=Depends(security.auth)):
    """Erneute Suche mit angepassten Begriffen (nutzt die gespeicherte Bildsignatur, nicht das Bild)."""
    security.limit_user(user, "image", 10)
    row = db.one("SELECT * FROM searches WHERE id=? AND kind='image'", (sid,))
    if not row:
        raise HTTPException(404, "Bildrecherche nicht gefunden.")
    analysis = db.jload(row["payload"], {}).get("analysis", {})
    if analysis.get("contains_people"):
        raise HTTPException(403, "Mit Bildern, die Personen zeigen, wird keine Websuche durchgeführt.")
    svc = P.SearchService(db.get_settings())
    try:
        res = IR.search(svc, body.terms, analysis["signature"])
    except IR.ImageError as e:
        raise HTTPException(422, str(e))
    if not res["images"] and not res["pages"] and res["errors"]:
        raise HTTPException(502, " | ".join(res["errors"]))
    return res
