"""Bildrecherche: lokale Analyse (EXIF, OCR, QR, Farben, Hashes) + Suche nach ähnlichen Bildinhalten.

Bewusst KEINE Gesichtserkennung / biometrische Vorlagen / Personenidentifizierung. Ein einfacher Gesichts-Detektor
wird ausschließlich als Schutzschalter genutzt: Zeigt ein Bild Personen, wird keine Websuche mit dem Bild ausgeführt.
"""
import io
import re
import shutil
import subprocess
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, UnidentifiedImageError

from .. import config
from .. import providers as P

Image.MAX_IMAGE_PIXELS = 50_000_000
FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}


class ImageError(Exception):
    pass


def validate(data: bytes) -> tuple[str, Image.Image]:
    if not data:
        raise ImageError("Leere Datei.")
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
        img = Image.open(io.BytesIO(data))
        fmt = img.format or ""
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise ImageError("Die Datei ist kein gültiges Bild (erlaubt: JPEG, PNG, WebP, GIF).")
    if fmt not in FORMATS:
        raise ImageError(f"Bildformat {fmt or 'unbekannt'} wird nicht unterstützt (erlaubt: JPEG, PNG, WebP, GIF).")
    if img.width < 16 or img.height < 16:
        raise ImageError("Das Bild ist zu klein (mind. 16×16 px).")
    return FORMATS[fmt], img


def _rat(v) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return 0.0


def read_exif(img: Image.Image) -> tuple[dict, tuple[float, float] | None]:
    out: dict[str, str] = {}
    gps = None
    try:
        exif = img.getexif()
    except Exception:  # noqa: BLE001
        return out, None
    for tag, val in exif.items():
        name = ExifTags.TAGS.get(tag, str(tag))
        if isinstance(val, (bytes, bytearray)) or name in ("MakerNote", "UserComment", "GPSInfo"):
            continue
        out[name] = str(val)[:200]
    try:
        for tag, val in exif.get_ifd(0x8769).items():  # Exif-IFD
            name = ExifTags.TAGS.get(tag, str(tag))
            if not isinstance(val, (bytes, bytearray)) and name not in ("MakerNote", "UserComment"):
                out.setdefault(name, str(val)[:200])
        g = exif.get_ifd(0x8825)
        if g and 2 in g and 4 in g:
            def conv(c, ref):
                d = _rat(c[0]) + _rat(c[1]) / 60 + _rat(c[2]) / 3600
                return -d if ref in ("S", "W") else d
            gps = (conv(g[2], g.get(1)), conv(g[4], g.get(3)))
            out["GPS"] = f"{gps[0]:.5f}, {gps[1]:.5f}"
    except Exception:  # noqa: BLE001
        pass
    return out, gps


def work_copy(img: Image.Image, size: int = 1024) -> Image.Image:
    im = img.convert("RGB")
    im.thumbnail((size, size))
    return im


def signature(im: Image.Image) -> dict:
    g = im.convert("L").resize((9, 8))
    a = np.asarray(g, dtype=np.int16)
    dh = (a[:, 1:] > a[:, :-1]).flatten()
    h = int("".join("1" if b else "0" for b in dh), 2)
    small = np.asarray(im.resize((48, 48)), dtype=np.uint8) // 64  # 4 Stufen je Kanal
    idx = small[..., 0] * 16 + small[..., 1] * 4 + small[..., 2]
    hist = np.bincount(idx.flatten(), minlength=64).astype(float)
    hist /= hist.sum()
    return {"dhash": f"{h:016x}", "hist": [round(x, 4) for x in hist]}


def similarity(sig: dict, other: dict) -> float:
    ham = bin(int(sig["dhash"], 16) ^ int(other["dhash"], 16)).count("1")
    inter = float(np.minimum(np.array(sig["hist"]), np.array(other["hist"])).sum())
    return round((0.6 * (1 - ham / 64) + 0.4 * inter) * 100, 1)


def dominant_colors(im: Image.Image, n: int = 5) -> list[str]:
    q = im.resize((80, 80)).quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    return ["#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]) for _, i in counts[:n]]


def detect_people(im: Image.Image) -> int:
    """Schutzschalter: Anzahl vermuteter Gesichter (Haar-Cascade). Es werden keine Merkmale gespeichert."""
    import cv2
    gray = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    scale = 800 / max(h, w)
    if scale < 1:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
    ms = max(24, gray.shape[1] // 30)
    total = 0
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        c = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        total = max(total, len(c.detectMultiScale(gray, 1.1, 6, minSize=(ms, ms))))
    return total


def read_qr(im: Image.Image) -> str | None:
    import cv2
    try:
        txt, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
        return txt[:500] or None
    except Exception:  # noqa: BLE001
        return None


def ocr(im: Image.Image) -> tuple[str, bool]:
    """Texterkennung über das Tesseract-CLI (falls installiert). Rückgabe: (Text, verfügbar)."""
    exe = shutil.which("tesseract")
    if not exe:
        return "", False
    tmp = config.TMP_DIR / f"ocr-{uuid.uuid4().hex}.png"
    try:
        im.save(tmp, "PNG")
        for lang in ("deu+eng", "eng"):
            r = subprocess.run([exe, str(tmp), "stdout", "-l", lang, "--psm", "11"], capture_output=True, text=True, timeout=25)
            if r.returncode == 0:
                return r.stdout, True
        return "", True
    except (subprocess.SubprocessError, OSError):
        return "", True
    finally:
        tmp.unlink(missing_ok=True)


def terms_from_text(text: str, limit: int = 5) -> list[str]:
    cands: Counter = Counter()
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip(" -_|.,:;")
        letters = sum(c.isalpha() for c in line)
        if len(line) < 4 or len(line) > 40 or letters / max(1, len(line)) < 0.75:
            continue
        words = line.split()
        if len(words) > 4 or all(len(w) < 3 for w in words):
            continue
        cands[line] += len(line)
    return [t for t, _ in cands.most_common(limit)]


def analyze(data: bytes, include_exif: bool, svc: P.SearchService) -> dict:
    ext, img = validate(data)
    exif, gps = read_exif(img)
    im = work_copy(img)
    faces = detect_people(im)
    sig = signature(im)
    res: dict = {
        "format": ext.upper(), "width": img.width, "height": img.height, "size_kb": round(len(data) / 1024, 1),
        "colors": dominant_colors(im), "signature": sig, "contains_people": faces > 0,
        "exif": exif if include_exif else None, "exif_present": bool(exif), "gps_present": gps is not None,
        "ocr_text": "", "ocr_available": True, "qr": None, "place": None, "terms": [], "notes": [],
    }
    if faces:
        res["notes"].append("Das Bild zeigt vermutlich Personen. Aus Datenschutzgründen führt MOSI INTEL mit solchen Bildern keine Websuche durch und identifiziert keine Personen anhand von Gesichtern.")
        return res
    text, avail = ocr(im)
    res["ocr_text"], res["ocr_available"] = text.strip()[:2000], avail
    if not avail:
        res["notes"].append("Texterkennung (Tesseract) ist nicht installiert – Text/Logo-Schrift im Bild wird nicht ausgewertet.")
    res["qr"] = read_qr(im)
    terms = terms_from_text(text)
    if res["qr"]:
        dom = P.domain_of(res["qr"]) if res["qr"].startswith("http") else ""
        terms.append(dom or res["qr"][:60])
    if gps and svc.geocoding:
        res["place"] = svc.reverse_geocode(*gps)
        if res["place"]:
            terms.append(res["place"])
    elif gps:
        res["notes"].append("Das Bild enthält GPS-Daten. Ortsauflösung ist in den Settings deaktiviert (sendet Koordinaten an OpenStreetMap/Nominatim).")
    res["terms"] = list(dict.fromkeys(terms))[:6]
    if not res["terms"]:
        res["notes"].append("Aus dem Bild konnten keine Suchbegriffe abgeleitet werden (kein lesbarer Text/QR/Ort). Bitte Begriffe manuell eingeben.")
    return res


def _score(hit: P.Hit, sig: dict) -> P.Hit | None:
    if not hit.thumbnail:
        return None
    raw = P.safe_fetch(hit.thumbnail) if hit.thumbnail.startswith("http") else None
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
        hit.snippet = f"{hit.snippet}".strip()
        hit.published = str(similarity(sig, signature(work_copy(im, 256))))  # Ähnlichkeit in published zwischengespeichert
        return hit
    except Exception:  # noqa: BLE001
        return None


def search(svc: P.SearchService, terms: list[str], sig: dict) -> dict:
    terms = [t.strip() for t in terms if t.strip()][:4]
    if not terms:
        raise ImageError("Keine Suchbegriffe angegeben.")
    images: list[P.Hit] = []
    pages: list[P.Hit] = []
    errors: list[str] = []
    for t in terms:
        try:
            h, e = svc.images(t, 12)
            images += h
            errors += e
        except P.ProviderError as e:
            errors.append(str(e))
        try:
            h, e = svc.web(f'"{t}"' if " " in t else t, limit=5)
            pages += h
        except P.ProviderError as e:
            errors.append(str(e))
    images = P.dedupe(images)[:30]
    scored: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for src, out in zip(images, ex.map(lambda h: _score(P.Hit(**h.to_dict()), sig), images)):
            if out:
                scored[src.url] = float(out.published)
    res = []
    for h in images:
        d = h.to_dict()
        d.pop("published", None)
        d["similarity"] = scored.get(h.url)
        d["domain"] = P.domain_of(h.url)
        d["trust"] = P.trust(d["domain"])
        res.append(d)
    res.sort(key=lambda d: (d["similarity"] is None, -(d["similarity"] or 0)))
    web = []
    for h in P.dedupe(pages)[:15]:
        d = h.to_dict()
        d["domain"] = P.domain_of(h.url)
        d["trust"] = P.trust(d["domain"])
        web.append(d)
    return {"terms": terms, "images": res, "pages": web, "errors": sorted(set(errors))}


def store_image(data: bytes, ext: str) -> str:
    """Speichert ein Bild unter einem serverseitig erzeugten Namen (kein Nutzer-Dateiname → kein Path Traversal)."""
    name = f"{uuid.uuid4().hex}.{ext}"
    path: Path = config.IMAGE_DIR / name
    path.write_bytes(data)
    path.chmod(0o600)
    return name
