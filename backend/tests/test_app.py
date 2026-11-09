import io
import os
import tempfile

import pytest
from PIL import Image, ImageDraw

os.environ["MOSI_DATA_DIR"] = tempfile.mkdtemp()
os.environ["MOSI_ADMIN_PASSWORD"] = "testpasswort123"
os.environ["MOSI_MAX_UPLOAD_MB"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import providers as P  # noqa: E402
from app.main import app  # noqa: E402
from app.services import name_research  # noqa: E402


def fake_get(self, url, name, **kw):
    q = kw.get("params", {}).get("q", "") or kw.get("params", {}).get("srsearch", "")
    if "wikipedia" in url:
        return {"query": {"search": [
            {"title": "Max Mustermann (Politiker)", "snippet": "Max Mustermann ist ein <b>Politiker</b> der Beispielpartei.", "timestamp": "2024-01-02T00:00:00Z"},
            {"title": "Max Mustermann (Fußballspieler)", "snippet": "Max Mustermann ist ein Fußballspieler.", "timestamp": "2023-01-02T00:00:00Z"}]}}
    cat = kw.get("params", {}).get("categories")
    if cat == "images":
        return {"results": [{"title": "Brücke", "url": "https://example.org/a", "thumbnail_src": "https://example.org/t.jpg", "img_src": "https://example.org/a.jpg"}]}
    return {"results": [
        {"title": "Max Mustermann – Beispielpartei", "url": "https://www.example.org/team/max?utm_source=x", "content": "Max Mustermann ist Politiker bei der Beispielpartei. Kontakt max@example.org", "publishedDate": "2024-05-01T10:00:00"},
        {"title": "Max Mustermann – Beispielpartei", "url": "https://example.org/team/max", "content": "Duplikat"},
        {"title": "Max Mustermann in der Zeitung", "url": "https://www.spiegel.de/a", "content": "Max Mustermann wurde Politiker.", "publishedDate": "2024-04-01"},
        {"title": "Max Mustermann Bäcker in Köln", "url": "https://bäcker.example.com/x", "content": "Max Mustermann backt Brot."},
        {"title": "Anderer Max", "url": "https://other.example/x", "content": "Nicht relevant, kein Treffer"},
        {"title": "Max Mustermann Adresse", "url": "https://www.dasoertliche.de/x", "content": "Max Mustermann Tel 0170 1234567"},
    ]}


@pytest.fixture(scope="module")
def client():
    P.SearchService._get = fake_get
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "testpasswort123"})
    assert r.status_code == 200
    client.post("/api/settings/", headers={})
    h = {"X-CSRF-Token": r.json()["csrf"]}
    client.put("/api/settings", json={"searxng_url": "http://searx.local"}, headers=h)
    return h


def png(w=200, h=100, text=None):
    im = Image.new("RGB", (w, h), (30, 90, 200))
    if text:
        ImageDraw.Draw(im).text((10, 10), text, fill=(255, 255, 255))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def test_requires_login(client):
    assert client.get("/api/research").status_code == 401


def test_bad_login(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "falsch"}).status_code == 401


def test_csrf_enforced(client, auth):
    assert client.post("/api/research", json={"title": "x"}).status_code == 403


def test_origin_check(client, auth):
    r = client.post("/api/research", json={"title": "x"}, headers={**auth, "Origin": "http://evil.example"})
    assert r.status_code == 403


def test_status(client, auth):
    r = client.get("/api/system/status").json()
    assert r["database"]["ok"] and r["search_ready"] and r["memory_mb"]


def test_web_search_dedup_and_domain_filter(client, auth):
    r = client.post("/api/web-search", json={"queries": ["max mustermann"]}, headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    urls = [x["url"] for x in d["results"]]
    assert sum("example.org/team/max" in u for u in urls) == 1 and d["duplicates_removed"] >= 1
    r = client.post("/api/web-search", json={"queries": ["max"], "domains": ["spiegel.de"]}, headers=auth).json()
    assert [x["domain"] for x in r["results"]] == ["spiegel.de"]
    assert r["results"][0]["trust"]["level"] == "high"


def test_web_search_validation(client, auth):
    assert client.post("/api/web-search", json={"queries": [" "]}, headers=auth).status_code == 422
    assert client.post("/api/web-search", json={"queries": ["a"], "domains": ["no spaces!"]}, headers=auth).status_code == 422


def test_name_research_privacy_and_disambiguation(client, auth):
    r = client.post("/api/name-research", json={"name": "Max Mustermann", "context": "Politiker", "organization": "Beispielpartei", "region": "", "purpose": "public_figure"}, headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    text = str(d)
    assert "max@example.org" not in text and "[E-Mail entfernt]" in text
    assert "dasoertliche" not in text  # Broker ausgeblendet
    assert d["stats"]["dropped_no_name_match"] >= 1
    assert len(d["namesakes"]) == 2
    confirmed = [i for s in d["sections"].values() for i in s["items"] if i["match"] == "confirmed"]
    assert confirmed and any(u["domain"] == "bäcker.example.com" for u in d["unconfirmed"])
    assert all(i["retrieved_at"] and i["trust"] for i in confirmed)


def test_name_research_self_shows_brokers(client, auth):
    d = client.post("/api/name-research", json={"name": "Max Mustermann", "purpose": "self"}, headers=auth).json()
    assert any(x["broker"] for x in d["domains"])
    assert "0170" not in str(d)


@pytest.mark.parametrize("bad", [{"name": "max@example.org"}, {"name": "Max", "context": "Telefon +49 170 1234567"}, {"name": "https://x.de"}])
def test_name_research_rejects_contact_data(client, auth, bad):
    r = client.post("/api/name-research", json={"purpose": "self", **bad}, headers=auth)
    assert r.status_code == 422


def test_name_research_requires_purpose(client, auth):
    assert client.post("/api/name-research", json={"name": "Max Mustermann"}, headers=auth).status_code == 422


def test_image_validation(client, auth):
    r = client.post("/api/image-research", files={"file": ("x.png", b"not an image", "image/png")}, headers=auth)
    assert r.status_code == 422
    r = client.post("/api/image-research", files={"file": ("big.png", b"0" * (2 * 1024 * 1024), "image/png")}, headers=auth)
    assert r.status_code == 413


def test_image_analysis_exif_and_not_stored(client, auth, monkeypatch):
    monkeypatch.setattr(P, 'safe_fetch', lambda url, **k: png(60, 40))
    before = len(os.listdir(os.environ["MOSI_DATA_DIR"] + "/images"))
    r = client.post("/api/image-research", files={"file": ("../../etc/passwd.png", png(), "image/png")}, data={"include_exif": "true"}, headers=auth)
    assert r.status_code == 200, r.text
    a = r.json()["analysis"]
    assert a["width"] == 200 and a["format"] == "PNG" and not a["contains_people"] and a["exif"] == {}
    assert len(a["colors"]) >= 1 and a["image_saved"] is False
    assert len(os.listdir(os.environ["MOSI_DATA_DIR"] + "/images")) == before
    assert os.listdir(os.environ["MOSI_DATA_DIR"] + "/tmp") == []


def test_image_search_with_terms(client, auth, monkeypatch):
    monkeypatch.setattr(P, 'safe_fetch', lambda url, **k: png(60, 40))
    r = client.post("/api/image-research", files={"file": ("a.png", png(), "image/png")}, headers=auth).json()
    r2 = client.post(f"/api/image-research/{r['id']}/search", json={"terms": ["Brücke"]}, headers=auth)
    assert r2.status_code == 200, r2.text
    img = r2.json()["images"][0]
    assert img["similarity"] is not None and img["similarity"] > 90 and img["domain"] == "example.org"


def test_people_images_are_blocked(client, auth, monkeypatch):
    from app.services import image_research as IR
    monkeypatch.setattr(IR, "detect_people", lambda im: 1)
    r = client.post("/api/image-research", files={"file": ("a.png", png(), "image/png")}, headers=auth).json()
    assert r["analysis"]["contains_people"] and r["search"] is None
    assert client.post(f"/api/image-research/{r['id']}/search", json={"terms": ["x"]}, headers=auth).status_code == 403


def test_project_lifecycle_and_reports(client, auth):
    pid = client.post("/api/research", json={"title": "Test Projekt äöü", "description": "Beschreibung"}, headers=auth).json()["id"]
    item = {"title": "Quelle 1 – „Test“", "summary": "Zusammenfassung", "url": "https://www.spiegel.de/a", "source_domain": "spiegel.de", "trust_level": "high", "trust_score": 85,
            "category": "Nachrichten", "published": "2024-04-01", "retrieved_at": "2025-01-01 10:00 UTC"}
    r = client.post(f"/api/research/{pid}/items", json=item, headers=auth)
    assert r.status_code == 201
    iid = r.json()["id"]
    assert client.post(f"/api/research/{pid}/items", json=item, headers=auth).status_code == 409
    assert client.post(f"/api/research/{pid}/items", json={**item, "url": "javascript:alert(1)"}, headers=auth).status_code == 422
    client.patch(f"/api/research/{pid}/items/{iid}", json={"note": "wichtig", "category": "Beruflich"}, headers=auth)
    client.post(f"/api/research/{pid}/notes", json={"text": "Eine Notiz"}, headers=auth)
    p = client.get(f"/api/research/{pid}").json()
    assert p["items"][0]["note"] == "wichtig" and p["notes"][0]["text"] == "Eine Notiz"
    assert client.get("/api/local-search", params={"q": "Zusammen"}).json()["items"]
    pdf = client.post("/api/reports/export", json={"project_id": pid, "format": "pdf"}, headers=auth)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 2000
    html = client.post("/api/reports/export", json={"project_id": pid, "format": "html"}, headers=auth).text
    assert "Test Projekt" in html and "Datenqualität" in html
    js = client.post("/api/reports/export", json={"project_id": pid, "format": "json"}, headers=auth).json()
    assert js["sources"][0]["domain"] == "spiegel.de"
    client.patch(f"/api/research/{pid}", json={"archived": True}, headers=auth)
    assert pid in [x["id"] for x in client.get("/api/research", params={"archived": True}).json()]
    assert client.delete(f"/api/research/{pid}", headers=auth).status_code == 200
    assert client.get(f"/api/research/{pid}").status_code == 404


def test_dashboard(client, auth):
    d = client.get("/api/dashboard").json()
    assert d["stats"]["searches_total"] >= 1 and d["recent_searches"]


def test_provider_error_is_visible_not_faked(client, auth):
    def boom(self, url, name, **kw):
        raise P.ProviderError("SearXNG: nicht erreichbar (ConnectError).")
    orig = P.SearchService._get
    P.SearchService._get = boom
    try:
        r = client.post("/api/web-search", json={"queries": ["x"]}, headers=auth)
        assert r.status_code == 502 and "nicht erreichbar" in r.json()["detail"]
    finally:
        P.SearchService._get = orig


def test_password_change_and_logout(client, auth):
    assert client.post("/api/auth/password", json={"current_password": "falsch", "new_password": "neuespasswort123"}, headers=auth).status_code == 400
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/research").status_code == 401


def test_ssrf_guard():
    assert P.safe_fetch("http://127.0.0.1:8000/x") is None
    assert P.safe_fetch("http://169.254.169.254/latest") is None
    assert P.safe_fetch("file:///etc/passwd") is None


def test_name_helpers():
    assert name_research.norm("Müller, Jörg") == "muller jorg"
    assert name_research.name_match(name_research.norm("Mueller Max"), name_research.tokens("Max Mueller"))
