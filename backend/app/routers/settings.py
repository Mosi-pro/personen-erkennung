from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config, db, providers, security

router = APIRouter(prefix="/api/settings", tags=["settings"])


def public_view() -> dict:
    s = db.get_settings()
    key = s.get("brave_api_key") or config.DEFAULT_BRAVE_KEY
    return {
        "searxng_url": s.get("searxng_url", config.DEFAULT_SEARXNG_URL),
        "brave_configured": bool(key), "brave_hint": ("••••" + key[-4:]) if len(key) >= 8 else ("••••" if key else ""),
        "wiki_langs": s.get("wiki_langs", "de,en"),
        "geocoding_enabled": s.get("geocoding_enabled") == "1",
        "result_limit": int(s.get("result_limit") or 10),
    }


class SettingsIn(BaseModel):
    searxng_url: str | None = Field(None, max_length=300)
    brave_api_key: str | None = Field(None, max_length=200)  # None = unverändert, "" = löschen
    wiki_langs: str | None = Field(None, max_length=40)
    geocoding_enabled: bool | None = None
    result_limit: int | None = Field(None, ge=5, le=30)


@router.get("")
def get_settings(user=Depends(security.auth)):
    return public_view()


@router.put("")
def put_settings(body: SettingsIn, user=Depends(security.auth)):
    if body.searxng_url is not None:
        u = body.searxng_url.strip()
        if u:
            p = urlparse(u)
            if p.scheme not in ("http", "https") or not p.hostname:
                raise HTTPException(422, "SearXNG-URL muss mit http:// oder https:// beginnen.")
        db.set_setting("searxng_url", u.rstrip("/"))
    if body.brave_api_key is not None:
        db.set_setting("brave_api_key", body.brave_api_key.strip())
    if body.wiki_langs is not None:
        langs = [x.strip() for x in body.wiki_langs.split(",") if x.strip()]
        if not langs or any(not (2 <= len(x) <= 3 and x.isalpha() and x.islower()) for x in langs):
            raise HTTPException(422, "Wikipedia-Sprachen: kommagetrennte Codes wie „de,en“.")
        db.set_setting("wiki_langs", ",".join(langs))
    if body.geocoding_enabled is not None:
        db.set_setting("geocoding_enabled", "1" if body.geocoding_enabled else "0")
    if body.result_limit is not None:
        db.set_setting("result_limit", str(body.result_limit))
    return public_view()


@router.post("/test/{name}")
def test_provider(name: str, user=Depends(security.auth)):
    security.limit_user(user, "test", 10)
    try:
        return {"ok": True, "message": providers.SearchService(db.get_settings()).test(name)}
    except providers.ProviderError as e:
        return {"ok": False, "message": str(e)}
