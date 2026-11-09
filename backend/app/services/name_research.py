"""Namensrecherche für öffentlich auftretende Personen/Organisationen und zur Selbstauskunft.

Es werden nur Suchtreffer-Auszüge ausgewertet (keine Seiten gecrawlt). Treffer werden nur dann einem Namen
zugeordnet, wenn alle Namensbestandteile im Beleg stehen; Kontext-Übereinstimmung wird separat ausgewiesen.
"""
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .. import providers as P

SECTIONS = {
    "career": "Beruflicher Hintergrund",
    "activities": "Öffentliche Tätigkeiten",
    "organizations": "Unternehmen und Organisationen",
    "publications": "Veröffentlichungen",
    "news": "Nachrichtenberichte",
    "press": "Pressemitteilungen",
    "official": "Offizielle Webseiten",
}
PUB_DOMAINS = {"orcid.org", "researchgate.net", "scholar.google.com", "arxiv.org", "doi.org", "semanticscholar.org", "dblp.org",
               "nature.com", "sciencedirect.com", "springer.com", "dnb.de", "books.google.com", "amazon.de", "goodreads.com"}
PROFILE_DOMAINS = {"linkedin.com", "xing.com", "github.com", "gitlab.com", "crunchbase.com", "wikipedia.org", "wikidata.org",
                   "abgeordnetenwatch.de", "bundestag.de", "northdata.de"}
PRESS_RE = re.compile(r"pressemitteilung|press release|pressemeldung|/presse|newsroom|/press/", re.I)
ORG_RE = re.compile(r"\b(verein|e\.v\.|stiftung|foundation|association|club|gmbh|ag|inc|ltd|gemeinde|universität|university|institut|institute|partei|verband)\b", re.I)
STOP = {"und", "der", "die", "das", "von", "van", "the", "and", "for", "bei", "mit", "aus", "für", "gmbh", "inc", "ltd"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(?<!\w)(\+?\d[\d\s/().-]{7,}\d)(?!\w)")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def tokens(s: str, min_len: int = 2) -> list[str]:
    return [t for t in norm(s).split() if len(t) >= min_len and t not in STOP]


def redact(s: str) -> str:
    return PHONE.sub("[Telefonnr. entfernt]", EMAIL.sub("[E-Mail entfernt]", s or ""))


def validate_inputs(name: str, context: str, org: str, region: str) -> str | None:
    """Gibt eine Fehlermeldung zurück, wenn die Eingabe keine Namensrecherche ist."""
    n = name.strip()
    if len(n) < 2 or len(n) > 100:
        return "Der Name muss 2–100 Zeichen lang sein."
    for label, v in (("Name", n), ("Kontext", context), ("Organisation", org), ("Region", region)):
        if "@" in v or re.search(r"https?://|www\.", v, re.I):
            return f"{label}: E-Mail-Adressen und URLs sind keine gültige Eingabe (keine Recherche zu Kontaktdaten)."
        if PHONE.search(v):
            return f"{label}: Telefonnummern sind keine gültige Eingabe."
    if sum(ch.isdigit() for ch in n) > 3:
        return "Der Name enthält zu viele Ziffern."
    if re.search(r"\b(passwort|password|wohnadresse|privatadresse|handynummer|telefonnummer)\b", " ".join([n, context, org, region]), re.I):
        return "Recherchen zu privaten Kontaktdaten oder Zugangsdaten werden nicht unterstützt."
    return None


def name_match(text_n: str, name_tokens: list[str]) -> bool:
    words = set(text_n.split())
    return all(t in words for t in name_tokens)


def run(svc: P.SearchService, name: str, context: str, org: str, region: str, purpose: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    name = name.strip()
    ntok = tokens(name)
    ctx_tok = [t for t in tokens(context, 3)]
    org_tok = tokens(org, 3)
    reg_tok = tokens(region, 3)
    has_ctx = bool(ctx_tok or org_tok or reg_tok)
    self_mode = purpose == "self"
    pages = 2 if self_mode else 1

    extra = " ".join(x for x in (org, context, region) if x.strip())
    q = f'"{name}"'
    jobs: list[tuple[str, str, bool, int]] = [("general", f"{q} {extra}".strip(), False, p) for p in range(1, pages + 1)]
    jobs += [("news", f"{q} {org or context}".strip(), True, 1),
             ("press", f"{q} Pressemitteilung OR \"press release\" {org}".strip(), False, 1),
             ("pubs", f"{q} Veröffentlichung OR publication OR Interview OR Vortrag", False, 1),
             ("profile", f"{q} LinkedIn OR Xing OR ORCID OR GitHub", False, 1)]
    if org.strip():
        jobs.append(("org", f"{q} \"{org.strip()}\"", False, 1))
    if self_mode:
        jobs.append(("self_social", f"{q} Profil OR profile", False, 1))

    raw: list[tuple[str, P.Hit]] = []
    errors: list[str] = []
    has_web = bool(svc.configured())

    def work(job):
        kind, query, news, page = job
        return kind, svc.web(query, news=news, page=page)

    if has_web:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(work, j) for j in jobs]
            for f in futs:
                try:
                    kind, (hits, errs) = f.result(timeout=60)
                    raw += [(kind, h) for h in hits]
                    errors += errs
                except P.ProviderError as e:
                    errors.append(str(e))
                except Exception as e:  # noqa: BLE001
                    errors.append(f"Fehler bei Suche: {type(e).__name__}")
    else:
        errors.append("Kein Websuch-Anbieter konfiguriert – es werden nur Wikipedia-Ergebnisse angezeigt. Für vollständige Ergebnisse SearXNG oder Brave in den Settings einrichten.")

    wiki_hits: list[P.Hit] = []
    try:
        wiki_hits = svc.wikipedia(f"\"{name}\" {org}".strip() if org else name)
    except P.ProviderError as e:
        errors.append(str(e))
    raw += [("wiki", h) for h in wiki_hits]

    # Auswerten
    items: list[dict] = []
    dropped_name = dropped_broker = 0
    seen = set()
    all_hits = P.dedupe([h for _, h in raw])
    kind_of = {P.norm_url(h.url): k for k, h in raw}
    for h in all_hits:
        dom = P.domain_of(h.url)
        broker = P.is_broker(dom)
        if broker and not self_mode:
            dropped_broker += 1
            continue
        text_n = norm(f"{h.title} {h.snippet} {dom} {h.url}")
        if not name_match(text_n, ntok):
            dropped_name += 1
            continue
        kind = kind_of.get(P.norm_url(h.url), "general")
        body_n = norm(f"{h.title} {h.snippet}")
        confirmed = False
        matched: list[str] = []
        if has_ctx:
            for t in set(ctx_tok + reg_tok):
                if t in body_n.split():
                    matched.append(t)
            otm = [t for t in org_tok if t in body_n.split() or t in dom.replace("-", "").replace(".", "")]
            matched += otm
            confirmed = bool(matched) and (not org_tok or len(otm) >= max(1, len(org_tok) // 2) or bool(set(matched) - set(otm)))
        match = "confirmed" if confirmed else ("unconfirmed" if has_ctx else "name_only")
        section = classify(h, dom, kind, org_tok, ntok)
        if broker:
            section = "activities"
        t = P.trust(dom)
        items.append({
            "title": redact(h.title), "summary": redact(h.snippet), "url": h.url, "domain": dom,
            "published": h.published, "retrieved_at": now, "trust": t, "match": match, "matched_terms": sorted(set(matched)),
            "section": section, "provider": h.provider, "broker": broker,
        })
    order = {"confirmed": 0, "name_only": 1, "unconfirmed": 2}
    items.sort(key=lambda i: (order[i["match"]], -i["trust"]["score"], i["published"] or ""), reverse=False)
    # stabil: bestätigt zuerst, dann Vertrauen absteigend
    items.sort(key=lambda i: (order[i["match"]], -i["trust"]["score"]))

    sections = {k: [] for k in SECTIONS}
    unconfirmed = []
    for it in items:
        if it["match"] == "unconfirmed":
            unconfirmed.append(it)
        else:
            sections[it["section"]].append(it)

    namesakes = []
    for h in wiki_hits:
        title = h.title.rsplit(" – Wikipedia", 1)[0]
        if name_match(norm(title), ntok):
            key = (title.lower())
            if key in seen:
                continue
            seen.add(key)
            namesakes.append({"title": title, "url": h.url, "hint": redact(h.snippet)})

    domains: dict[str, dict] = {}
    for it in items:
        d = domains.setdefault(it["domain"], {"domain": it["domain"], "count": 0, "trust": it["trust"], "broker": it["broker"], "sample_url": it["url"]})
        d["count"] += 1
    domain_list = sorted(domains.values(), key=lambda d: (-d["count"], -d["trust"]["score"]))

    warnings = []
    if not has_ctx and len(namesakes) > 1:
        warnings.append(f"Der Name ist nicht eindeutig: {len(namesakes)} mögliche Personen/Begriffe gefunden. Mit beruflichem Kontext, Organisation oder Region lässt sich die richtige Person eingrenzen.")
    elif not has_ctx:
        warnings.append("Ohne Kontext (Beruf, Organisation, Region) können Treffer verschiedene Personen mit gleichem Namen betreffen.")
    if unconfirmed:
        warnings.append(f"{len(unconfirmed)} Treffer enthalten den Namen, aber keinen Beleg für den angegebenen Kontext – sie werden separat als unbestätigt geführt (möglicherweise andere Personen).")
    if dropped_broker:
        warnings.append(f"{dropped_broker} Treffer von Personensuch-/Datenbroker-Seiten wurden ausgeblendet.")
    if any(i["broker"] for i in items):
        warnings.append("Es wurden Personensuch-/Datenbroker-Seiten gefunden, die deinen Namen führen. Dort kannst du meist die Löschung deines Eintrags verlangen (DSGVO Art. 17).")

    return {
        "query": {"name": name, "context": context, "organization": org, "region": region, "purpose": purpose},
        "retrieved_at": now,
        "summary": build_summary(name, items, has_ctx),
        "sections": {k: {"label": SECTIONS[k], "items": v} for k, v in sections.items()},
        "unconfirmed": unconfirmed,
        "namesakes": namesakes[:12],
        "domains": domain_list,
        "warnings": warnings,
        "errors": sorted(set(errors)),
        "stats": {"total": len(items), "confirmed": sum(i["match"] == "confirmed" for i in items), "dropped_no_name_match": dropped_name,
                  "dropped_brokers": dropped_broker, "domains": len(domain_list),
                  "providers": sorted({i["provider"] for i in items})},
        "sources": [{"n": n + 1, "title": i["title"], "url": i["url"], "domain": i["domain"], "published": i["published"],
                     "retrieved_at": i["retrieved_at"], "trust": i["trust"]} for n, i in enumerate(items)],
    }


def classify(h: P.Hit, dom: str, kind: str, org_tok: list[str], ntok: list[str]) -> str:
    blob = f"{h.title} {h.url}"
    dn = dom.replace("-", "").replace(".", "")
    if h.news or kind == "news" or P._in(dom, P.NEWS_DOMAINS):
        return "press" if PRESS_RE.search(blob) else "news"
    if PRESS_RE.search(blob) or kind == "press":
        return "press"
    if any(dom == d or dom.endswith("." + d) for d in PUB_DOMAINS) or kind == "pubs" and re.search(r"\.pdf$|publication|veröffentlich|paper|journal", blob, re.I):
        return "publications"
    if any(dom == d or dom.endswith("." + d) for d in PROFILE_DOMAINS) or kind == "profile":
        return "career"
    if (org_tok and all(t in dn for t in org_tok[:1])) or all(t in dn for t in ntok):
        return "official"
    if ORG_RE.search(f"{h.title} {h.snippet}") or kind == "org":
        return "organizations"
    return "activities"


def build_summary(name: str, items: list[dict], has_ctx: bool) -> str:
    if not items:
        return f"Zu „{name}“ wurden in den abgefragten Quellen keine belegbaren öffentlichen Treffer gefunden."
    pool = [i for i in items if i["match"] == "confirmed"] or [i for i in items if i["match"] == "name_only"]
    pool = [i for i in pool if i["summary"] and not i["broker"]]
    pool.sort(key=lambda i: -i["trust"]["score"])
    parts = []
    for i in pool[:3]:
        n = items.index(i) + 1
        parts.append(f"{i['summary']} [Quelle {n}: {i['domain']}]")
    head = f"Automatisch zusammengestellt aus Auszügen von {len(items)} Fundstellen (keine eigene Bewertung, bitte Originalquellen prüfen). "
    return head + (" ".join(parts) if parts else "Die Fundstellen enthalten keine auswertbaren Textauszüge.")
