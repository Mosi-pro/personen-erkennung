"""Suchanbieter-Adapter (SearXNG, Brave Search API, Wikipedia API), Quellenbewertung, sicherer Abruf.

Es werden ausschließlich dokumentierte APIs genutzt, kein Scraping von Suchmaschinen.
"""
import html
import ipaddress
import re
import socket
from dataclasses import asdict, dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from . import config

UA = f"MOSI-INTEL/{config.VERSION} (self-hosted research tool)"
TIMEOUT = httpx.Timeout(15.0, connect=6.0)


class ProviderError(Exception):
    pass


@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""
    published: str | None = None
    thumbnail: str | None = None
    img_src: str | None = None
    provider: str = ""
    news: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------- URL / Domain ----------------
TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_)", re.I)


def domain_of(url: str) -> str:
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def norm_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url
    q = urlencode([(k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)])
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return urlunparse(("https", host, p.path.rstrip("/") or "/", "", q, ""))


def dedupe(hits: list[Hit]) -> list[Hit]:
    seen, out = set(), []
    for h in hits:
        k = norm_url(h.url)
        t = (domain_of(h.url), re.sub(r"\W+", "", h.title.lower()))
        if k in seen or (t[1] and t in seen):
            continue
        seen.add(k)
        seen.add(t)
        out.append(h)
    return out


def clean_text(s: str | None, limit: int = 400) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", "", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


# ---------------- Quellenbewertung (Heuristik) ----------------
NEWS_DOMAINS = {
    "tagesschau.de", "zdf.de", "ard.de", "br.de", "ndr.de", "wdr.de", "mdr.de", "swr.de", "hr.de", "rbb24.de", "deutschlandfunk.de",
    "spiegel.de", "zeit.de", "faz.net", "sueddeutsche.de", "handelsblatt.com", "welt.de", "taz.de", "stern.de", "focus.de",
    "fr.de", "tagesspiegel.de", "dw.com", "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "theguardian.com", "nytimes.com",
    "washingtonpost.com", "ft.com", "economist.com", "bloomberg.com", "aljazeera.com", "nzz.ch", "derstandard.at", "orf.at",
    "srf.ch", "lemonde.fr", "npr.org", "cnn.com", "wsj.com", "heise.de", "golem.de",
}
REFERENCE = {"wikipedia.org", "wikidata.org", "britannica.com", "dnb.de", "deutsche-digitale-bibliothek.de", "orcid.org", "doi.org",
             "arxiv.org", "dblp.org", "semanticscholar.org", "nature.com", "sciencedirect.com", "springer.com", "bundestag.de"}
PROFESSIONAL = {"linkedin.com", "xing.com", "github.com", "gitlab.com", "researchgate.net", "crunchbase.com", "scholar.google.com",
                "abgeordnetenwatch.de", "bloomberg.com", "northdata.de", "handelsregister.de", "unternehmensregister.de"}
USER_GENERATED = {"facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com", "pinterest.com", "reddit.com", "quora.com",
                  "youtube.com", "tumblr.com", "wordpress.com", "blogspot.com", "medium.com", "gutefrage.net", "vk.com", "telegram.org"}
# Personensuch- und Datenbroker-Seiten (Privatpersonen-Profile) – für Dritt-Recherchen ausgeblendet
BROKERS = {"spokeo.com", "whitepages.com", "192.com", "dastelefonbuch.de", "dasoertliche.de", "11880.com", "pipl.com", "truthfinder.com",
           "beenverified.com", "intelius.com", "radaris.com", "mylife.com", "peekyou.com", "zabasearch.com", "fastpeoplesearch.com",
           "truepeoplesearch.com", "thatsthem.com", "ancientfaces.com", "clustrmaps.com", "kennstdueinen.de", "personensuche.com",
           "yasni.de", "yasni.com", "123people.de", "stayfriends.de", "geneanet.org", "rehold.com"}


def _in(domain: str, group: set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in group)


def is_broker(domain: str) -> bool:
    return _in(domain, BROKERS)


def trust(domain: str) -> dict:
    """Vertrauenswürdigkeit der Quelle (heuristisch, anhand der Domain)."""
    if not domain:
        return {"level": "unknown", "score": 0, "label": "Unbekannt"}
    if re.search(r"\.(gov|edu|mil)(\.[a-z]{2})?$", domain) or domain.endswith(("bund.de", "europa.eu", ".gv.at", "admin.ch", "bundestag.de")):
        return {"level": "high", "score": 92, "label": "Behörde / Hochschule"}
    if _in(domain, NEWS_DOMAINS):
        return {"level": "high", "score": 85, "label": "Etabliertes Nachrichtenmedium"}
    if _in(domain, REFERENCE):
        return {"level": "high", "score": 80, "label": "Nachschlagewerk / Fachdatenbank"}
    if _in(domain, PROFESSIONAL):
        return {"level": "medium", "score": 62, "label": "Berufliches Profil (selbst gepflegt)"}
    if is_broker(domain):
        return {"level": "low", "score": 15, "label": "Personensuch-/Datenbroker-Seite"}
    if _in(domain, USER_GENERATED):
        return {"level": "low", "score": 30, "label": "Nutzergenerierte Inhalte"}
    return {"level": "medium", "score": 50, "label": "Sonstige Webseite (ungeprüft)"}


# ---------------- Sicherer Abruf (SSRF-Schutz) ----------------
def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def safe_fetch(url: str, max_bytes: int = 1_500_000, timeout: float = 8.0) -> bytes | None:
    """Lädt eine öffentliche http(s)-URL (z. B. Vorschaubild); blockiert interne Ziele; folgt max. 3 Redirects."""
    try:
        for _ in range(4):
            p = urlparse(url)
            if p.scheme not in ("http", "https") or not p.hostname or not _public_host(p.hostname):
                return None
            with httpx.stream("GET", url, headers={"User-Agent": UA}, timeout=timeout, follow_redirects=False) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = str(httpx.URL(url).join(r.headers["location"]))
                    continue
                if r.status_code != 200:
                    return None
                if "image" not in r.headers.get("content-type", ""):
                    return None
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        return None
                return bytes(buf)
    except (httpx.HTTPError, ValueError):
        return None
    return None


# ---------------- Anbieter ----------------
TIME_BRAVE = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}
TIME_SEARX = {"day": "day", "week": "week", "month": "month", "year": "year"}


class SearchService:
    def __init__(self, settings: dict[str, str]):
        self.searxng = (settings.get("searxng_url") or config.DEFAULT_SEARXNG_URL).rstrip("/")
        self.brave = settings.get("brave_api_key") or config.DEFAULT_BRAVE_KEY
        self.wiki_langs = [x.strip() for x in (settings.get("wiki_langs") or "de,en").split(",") if re.fullmatch(r"[a-z]{2,3}", x.strip())] or ["de"]
        self.geocoding = settings.get("geocoding_enabled") == "1"
        self.limit = max(5, min(30, int(settings.get("result_limit") or 10)))

    def configured(self) -> list[str]:
        out = []
        if self.searxng:
            out.append("searxng")
        if self.brave:
            out.append("brave")
        return out

    # --- allgemeine Websuche über alle konfigurierten Anbieter ---
    def web(self, query: str, *, time_range: str = "any", news: bool = False, page: int = 1, limit: int | None = None, dedup: bool = True) -> tuple[list[Hit], list[str]]:
        limit = limit or self.limit
        hits: list[Hit] = []
        errors: list[str] = []
        providers = self.configured()
        if not providers:
            raise ProviderError("Kein Suchanbieter konfiguriert. Bitte unter Settings eine SearXNG-URL oder einen Brave-API-Schlüssel eintragen.")
        for name in providers:
            try:
                fn = self._searxng if name == "searxng" else self._brave
                hits += fn(query, time_range, news, page, limit)
            except ProviderError as e:
                errors.append(str(e))
        if not hits and errors and len(errors) == len(providers):
            raise ProviderError(" | ".join(errors))
        return (dedupe(hits) if dedup else hits), errors

    def images(self, query: str, limit: int = 12) -> tuple[list[Hit], list[str]]:
        hits, errors = [], []
        providers = self.configured()
        if not providers:
            raise ProviderError("Kein Bildsuch-Anbieter konfiguriert (SearXNG oder Brave erforderlich).")
        for name in providers:
            try:
                hits += self._searxng_images(query, limit) if name == "searxng" else self._brave_images(query, limit)
            except ProviderError as e:
                errors.append(str(e))
        if not hits and errors and len(errors) == len(providers):
            raise ProviderError(" | ".join(errors))
        return dedupe(hits), errors

    # --- SearXNG ---
    def _get(self, url: str, name: str, **kw) -> dict:
        try:
            r = httpx.get(url, timeout=TIMEOUT, headers={"User-Agent": UA, **kw.pop("headers", {})}, **kw)
        except httpx.HTTPError as e:
            raise ProviderError(f"{name}: nicht erreichbar ({type(e).__name__}).")
        if r.status_code == 401 or r.status_code == 403:
            raise ProviderError(f"{name}: Zugriff verweigert (API-Schlüssel / JSON-Format prüfen).")
        if r.status_code == 429:
            raise ProviderError(f"{name}: Kontingent/Rate-Limit erreicht.")
        if r.status_code != 200:
            raise ProviderError(f"{name}: HTTP {r.status_code}.")
        try:
            return r.json()
        except ValueError:
            raise ProviderError(f"{name}: ungültige Antwort (ist das JSON-Format in SearXNG aktiviert?).")

    def _searxng(self, q: str, tr: str, news: bool, page: int, limit: int) -> list[Hit]:
        params = {"q": q, "format": "json", "categories": "news" if news else "general", "pageno": page}
        if tr in TIME_SEARX:
            params["time_range"] = TIME_SEARX[tr]
        data = self._get(f"{self.searxng}/search", "SearXNG", params=params)
        out = []
        for r in data.get("results", [])[:limit]:
            if not r.get("url"):
                continue
            out.append(Hit(clean_text(r.get("title"), 200) or r["url"], r["url"], clean_text(r.get("content")),
                           (r.get("publishedDate") or "")[:10] or None, None, None, "searxng", news))
        return out

    def _searxng_images(self, q: str, limit: int) -> list[Hit]:
        data = self._get(f"{self.searxng}/search", "SearXNG", params={"q": q, "format": "json", "categories": "images"})
        out = []
        for r in data.get("results", [])[:limit]:
            page = r.get("url")
            if not page:
                continue
            out.append(Hit(clean_text(r.get("title"), 200) or page, page, clean_text(r.get("content"), 200), None,
                           r.get("thumbnail_src") or r.get("thumbnail") or r.get("img_src"), r.get("img_src"), "searxng"))
        return out

    # --- Brave Search API ---
    def _brave(self, q: str, tr: str, news: bool, page: int, limit: int) -> list[Hit]:
        params = {"q": q, "count": min(limit, 20), "offset": max(0, page - 1)}
        if tr in TIME_BRAVE:
            params["freshness"] = TIME_BRAVE[tr]
        ep = "news" if news else "web"
        data = self._get(f"https://api.search.brave.com/res/v1/{ep}/search", "Brave", params=params,
                         headers={"X-Subscription-Token": self.brave, "Accept": "application/json"})
        res = data.get("results") if news else (data.get("web") or {}).get("results")
        out = []
        for r in res or []:
            if not r.get("url"):
                continue
            out.append(Hit(clean_text(r.get("title"), 200) or r["url"], r["url"], clean_text(r.get("description")),
                           (r.get("page_age") or "")[:10] or r.get("age"), (r.get("thumbnail") or {}).get("src"), None, "brave", news))
        return out

    def _brave_images(self, q: str, limit: int) -> list[Hit]:
        data = self._get("https://api.search.brave.com/res/v1/images/search", "Brave", params={"q": q, "count": min(limit, 20)},
                         headers={"X-Subscription-Token": self.brave, "Accept": "application/json"})
        out = []
        for r in data.get("results", []):
            page = r.get("url")
            if not page:
                continue
            out.append(Hit(clean_text(r.get("title"), 200) or page, page, "", None, (r.get("thumbnail") or {}).get("src"),
                           (r.get("properties") or {}).get("url"), "brave"))
        return out

    # --- Wikipedia (öffentliche MediaWiki-API) ---
    def wikipedia(self, query: str, limit: int = 6) -> list[Hit]:
        out: list[Hit] = []
        for lang in self.wiki_langs:
            data = self._get(f"https://{lang}.wikipedia.org/w/api.php", "Wikipedia",
                             params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": limit, "srprop": "snippet|timestamp"})
            for r in (data.get("query") or {}).get("search", []):
                title = r["title"]
                out.append(Hit(f"{title} – Wikipedia ({lang})", f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                               clean_text(r.get("snippet")), (r.get("timestamp") or "")[:10] or None, None, None, "wikipedia"))
        return out

    def reverse_geocode(self, lat: float, lon: float) -> str | None:
        try:
            data = self._get("https://nominatim.openstreetmap.org/reverse", "Nominatim",
                             params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 12})
        except ProviderError:
            return None
        a = data.get("address") or {}
        parts = [a.get("city") or a.get("town") or a.get("village") or a.get("county"), a.get("country")]
        return ", ".join(p for p in parts if p) or None

    # --- Verbindungstest ---
    def test(self, name: str) -> str:
        if name == "searxng":
            if not self.searxng:
                raise ProviderError("Keine SearXNG-URL konfiguriert.")
            self._searxng("test", "any", False, 1, 1)
            return "SearXNG antwortet korrekt (JSON-Format aktiv)."
        if name == "brave":
            if not self.brave:
                raise ProviderError("Kein Brave-API-Schlüssel konfiguriert.")
            self._brave("test", "any", False, 1, 1)
            return "Brave Search API antwortet, Schlüssel gültig."
        if name == "wikipedia":
            self.wikipedia("test", 1)
            return "Wikipedia-API erreichbar."
        raise ProviderError("Unbekannter Anbieter.")
