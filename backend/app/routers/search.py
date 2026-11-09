import re
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import db, providers as P, security
from ..services import name_research

router = APIRouter(prefix="/api", tags=["search"])


class WebSearchIn(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=5)
    time_range: Literal["any", "day", "week", "month", "year"] = "any"
    domains: list[str] = Field(default_factory=list, max_length=10)
    exclude_domains: list[str] = Field(default_factory=list, max_length=10)
    news: bool = False

    @field_validator("queries")
    @classmethod
    def q(cls, v):
        v = [x.strip() for x in v if x.strip()]
        if not v or any(len(x) > 300 for x in v):
            raise ValueError("Mindestens eine Suchanfrage (max. 300 Zeichen) erforderlich.")
        return v

    @field_validator("domains", "exclude_domains")
    @classmethod
    def d(cls, v):
        out = []
        for x in v:
            x = x.strip().lower()
            x = urlparse(x).hostname or x if "://" in x else x
            x = x[4:] if x.startswith("www.") else x
            if x and not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", x):
                raise ValueError(f"Ungültige Domain: {x}")
            if x:
                out.append(x)
        return out


def _in(dom: str, lst: list[str]) -> bool:
    return any(dom == d or dom.endswith("." + d) for d in lst)


@router.post("/web-search")
def web_search(body: WebSearchIn, user=Depends(security.auth)):
    security.limit_user(user, "search", 30)
    svc = P.SearchService(db.get_settings())
    results, errors = [], []
    for q in body.queries:
        qq = q + "".join(f" site:{d}" for d in body.domains[:1])
        try:
            hits, errs = svc.web(qq, time_range=body.time_range, news=body.news, dedup=False)
            errors += errs
            for h in hits:
                d = h.to_dict()
                d["query"] = q
                results.append(d)
        except P.ProviderError as e:
            errors.append(str(e))
    if not results and errors:
        raise HTTPException(502, " | ".join(sorted(set(errors))))
    total_raw = len(results)
    hits = P.dedupe([P.Hit(**{k: v for k, v in r.items() if k != "query"}) for r in results])
    qmap = {P.norm_url(r["url"]): r["query"] for r in results}
    out = []
    for h in hits:
        dom = P.domain_of(h.url)
        if body.domains and not _in(dom, body.domains):
            continue
        if body.exclude_domains and _in(dom, body.exclude_domains):
            continue
        d = h.to_dict()
        d.update({"domain": dom, "trust": P.trust(dom), "query": qmap.get(P.norm_url(h.url), ""), "retrieved_at": _now()})
        out.append(d)
    payload = {"results": out, "errors": sorted(set(errors)), "duplicates_removed": total_raw - len(hits)}
    sid = db.log_search("web", " · ".join(body.queries), body.model_dump(), payload, len(out))
    return {"id": sid, **payload, "count": len(out)}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class NameIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    context: str = Field("", max_length=150)
    organization: str = Field("", max_length=150)
    region: str = Field("", max_length=100)
    purpose: Literal["self", "public_figure", "organization"]


@router.post("/name-research")
def name_research_ep(body: NameIn, user=Depends(security.auth)):
    security.limit_user(user, "name", 10)
    err = name_research.validate_inputs(body.name, body.context, body.organization, body.region)
    if err:
        raise HTTPException(422, err)
    svc = P.SearchService(db.get_settings())
    result = name_research.run(svc, body.name, body.context, body.organization, body.region, body.purpose)
    if result["stats"]["total"] == 0 and result["errors"] and not any(result["stats"]["providers"]):
        raise HTTPException(502, " | ".join(result["errors"]))
    sid = db.log_search("name", body.name, body.model_dump(), result, result["stats"]["total"])
    return {"id": sid, **result}
