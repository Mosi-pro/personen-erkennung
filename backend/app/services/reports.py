"""Berichte aus Rechercheprojekten: JSON, HTML, PDF."""
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime

from fpdf import FPDF

from .. import config

TRUST_LABEL = {"high": "hoch", "medium": "mittel", "low": "niedrig", "unknown": "unbekannt"}
MATCH_LABEL = {"confirmed": "Kontext bestätigt", "name_only": "nur Name", "unconfirmed": "unbestätigt (ggf. Namensvetter)", "": "–"}


def ts(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%d.%m.%Y %H:%M")


def build(project: dict, items: list[dict], notes: list[dict]) -> dict:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for i in items:
        by_cat[i["category"]].append(i)
    trust = Counter(i["trust_level"] for i in items)
    quality = []
    if not items:
        quality.append("Das Projekt enthält noch keine Ergebnisse.")
    if trust.get("low"):
        quality.append(f"{trust['low']} Quelle(n) mit niedriger Vertrauenswürdigkeit (nutzergenerierte Inhalte/Datenbroker) – nur mit Vorsicht verwenden.")
    if trust.get("unknown"):
        quality.append(f"{trust['unknown']} Quelle(n) ohne Bewertung.")
    unc = sum(1 for i in items if i["match"] == "unconfirmed")
    if unc:
        quality.append(f"{unc} Ergebnis(se) sind nicht eindeutig der gesuchten Person/Organisation zugeordnet (möglicher Namensvetter).")
    no_date = sum(1 for i in items if not i["published"])
    if no_date:
        quality.append(f"Bei {no_date} Ergebnis(sen) ist kein Veröffentlichungsdatum verfügbar.")
    quality.append("Die Vertrauensbewertung ist eine Heuristik anhand der Domain und ersetzt keine inhaltliche Prüfung. Zusammenfassungen sind automatisch übernommene Textauszüge der Suchanbieter.")
    quality.append("Alle Angaben stammen aus öffentlich zugänglichen Quellen zum jeweiligen Abrufdatum und können sich geändert haben.")
    summary = (f"Das Projekt „{project['title']}“ umfasst {len(items)} Ergebnis(se) aus {len({i['source_domain'] for i in items if i['source_domain']})} Quellen-Domains "
               f"in {len(by_cat)} Kategorie(n) sowie {len(notes)} Notiz(en). Vertrauensverteilung: "
               + ", ".join(f"{TRUST_LABEL.get(k, k)} {v}" for k, v in trust.most_common()) + "." if items else
               f"Das Projekt „{project['title']}“ enthält noch keine Ergebnisse.")
    return {
        "title": project["title"], "description": project["description"], "created_at": ts(project["created_at"]),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"), "summary": summary,
        "categories": {k: v for k, v in sorted(by_cat.items())}, "notes": [{"text": n["text"], "created_at": ts(n["created_at"])} for n in notes],
        "sources": [{"title": i["title"], "url": i["url"], "domain": i["source_domain"], "published": i["published"], "retrieved_at": i["retrieved_at"],
                     "trust": TRUST_LABEL.get(i["trust_level"], i["trust_level"])} for i in items if i["url"]],
        "quality": quality, "generator": f"MOSI INTEL {config.VERSION}",
    }


def to_json(rep: dict) -> bytes:
    return json.dumps(rep, ensure_ascii=False, indent=2).encode()


CSS = """body{background:#fff;color:#161a22;font:15px/1.55 Inter,system-ui,sans-serif;margin:0}main{max-width:860px;margin:0 auto;padding:40px 24px}
header{border-bottom:2px solid #4388FF;padding-bottom:16px;margin-bottom:24px}.brand{font-weight:700;letter-spacing:.14em;font-size:12px;color:#4388FF}
h1{margin:6px 0 4px;font-size:28px}h2{margin-top:36px;font-size:18px;border-bottom:1px solid #dde2ea;padding-bottom:6px}.meta{color:#5c667a;font-size:13px}
.item{border:1px solid #dde2ea;border-radius:6px;padding:12px 14px;margin:10px 0;break-inside:avoid}.item h3{margin:0 0 4px;font-size:15px}
.tag{display:inline-block;font-size:11px;border:1px solid #c5cdda;border-radius:4px;padding:1px 6px;margin-right:6px;color:#44506a}
a{color:#2a62d4;word-break:break-all}.note{background:#f4f6fa;border-left:3px solid #4388FF;padding:8px 12px;margin:8px 0}li{margin:4px 0}
@media print{main{padding:0}}"""


def to_html(rep: dict) -> bytes:
    e = html.escape
    out = [f"<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{e(rep['title'])} – MOSI INTEL Bericht</title><style>{CSS}</style></head><body><main>",
           f"<header><div class='brand'>MOSI INTEL · RECHERCHEBERICHT</div><h1>{e(rep['title'])}</h1>"
           f"<div class='meta'>Projekt angelegt: {e(rep['created_at'])} · Bericht erstellt: {e(rep['generated_at'])}</div>"
           f"{('<p>' + e(rep['description']) + '</p>') if rep['description'] else ''}</header>",
           f"<h2>Zusammenfassung</h2><p>{e(rep['summary'])}</p><h2>Ergebnisse</h2>"]
    if not rep["categories"]:
        out.append("<p>Keine Ergebnisse.</p>")
    for cat, items in rep["categories"].items():
        out.append(f"<h3>{e(cat)} ({len(items)})</h3>")
        for i in items:
            out.append(f"<div class='item'><h3>{e(i['title'])}</h3><div><span class='tag'>Vertrauen: {e(TRUST_LABEL.get(i['trust_level'], ''))}</span>"
                       f"<span class='tag'>{e(MATCH_LABEL.get(i['match'], '–'))}</span><span class='tag'>Abruf: {e(i['retrieved_at'])}</span>"
                       f"{('<span class=tag>Veröffentlicht: ' + e(i['published']) + '</span>') if i['published'] else ''}</div>"
                       f"<p>{e(i['summary'])}</p>{('<div class=note>Notiz: ' + e(i['note']) + '</div>') if i['note'] else ''}"
                       f"{('<a href=\"' + e(i['url'], quote=True) + '\" rel=\"noopener noreferrer\">' + e(i['url']) + '</a>') if i['url'].startswith(('http://', 'https://')) else ''}</div>")
    if rep["notes"]:
        out.append("<h2>Notizen</h2>" + "".join(f"<div class='note'>{e(n['text'])}<div class='meta'>{e(n['created_at'])}</div></div>" for n in rep["notes"]))
    out.append("<h2>Quellenverzeichnis</h2><ol>" + "".join(
        f"<li>{e(s['title'])} – <a href=\"{e(s['url'], quote=True)}\" rel=\"noopener noreferrer\">{e(s['domain'] or s['url'])}</a> "
        f"<span class='meta'>(Abruf {e(s['retrieved_at'])}, Vertrauen {e(s['trust'])})</span></li>" for s in rep["sources"] if s["url"].startswith(("http://", "https://"))) + "</ol>")
    out.append("<h2>Hinweise zur Datenqualität</h2><ul>" + "".join(f"<li>{e(q)}</li>" for q in rep["quality"]) + f"</ul><p class='meta'>{e(rep['generator'])}</p></main></body></html>")
    return "".join(out).encode()


def l1(s: str) -> str:
    """fpdf2-Kernschriften sind Latin-1; nicht darstellbare Zeichen werden ersetzt."""
    s = (s or "").replace("–", "-").replace("—", "-").replace("„", '"').replace("“", '"').replace("”", '"').replace("’", "'").replace("…", "...")
    return s.encode("latin-1", "replace").decode("latin-1")


class PDF(FPDF):
    def header(self):
        self.set_fill_color(11, 13, 18)
        self.rect(0, 0, 210, 14, "F")
        self.set_xy(15, 4)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(67, 136, 255)
        self.cell(0, 6, "MOSI INTEL  |  RECHERCHEBERICHT")
        self.ln(14)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 128, 145)
        self.cell(0, 6, f"{l1(self.title_text)}  -  Seite {self.page_no()}/{{nb}}", align="C")


def to_pdf(rep: dict) -> bytes:
    pdf = PDF(format="A4")
    pdf.title_text = rep["title"][:60]
    pdf.alias_nb_pages()
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()

    def h(text, size=13, space=4):
        pdf.ln(space)
        pdf.set_font("Helvetica", "B", size)
        pdf.set_text_color(22, 26, 34)
        pdf.multi_cell(0, 7, l1(text), new_x="LMARGIN", new_y="NEXT")

    def p(text, size=10, color=(40, 46, 60), style=""):
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 5, l1(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(22, 26, 34)
    pdf.multi_cell(0, 10, l1(rep["title"]), new_x="LMARGIN", new_y="NEXT")
    p(f"Projekt angelegt: {rep['created_at']}   |   Bericht erstellt: {rep['generated_at']}", 9, (92, 102, 122))
    if rep["description"]:
        pdf.ln(2)
        p(rep["description"])
    pdf.set_draw_color(67, 136, 255)
    pdf.set_line_width(0.6)
    pdf.line(15, pdf.get_y() + 3, 195, pdf.get_y() + 3)
    pdf.ln(4)
    h("Zusammenfassung")
    p(rep["summary"])
    h("Ergebnisse")
    if not rep["categories"]:
        p("Keine Ergebnisse.")
    for cat, items in rep["categories"].items():
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(67, 136, 255)
        pdf.cell(0, 6, l1(f"{cat} ({len(items)})"), new_x="LMARGIN", new_y="NEXT")
        for i in items:
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(22, 26, 34)
            pdf.multi_cell(0, 5, l1(i["title"]), new_x="LMARGIN", new_y="NEXT")
            meta = f"Vertrauen: {TRUST_LABEL.get(i['trust_level'], '-')}  |  {MATCH_LABEL.get(i['match'], '-')}  |  Abruf: {i['retrieved_at']}"
            if i["published"]:
                meta += f"  |  Veroeffentlicht: {i['published']}"
            p(meta, 8, (92, 102, 122))
            if i["summary"]:
                p(i["summary"], 9)
            if i["note"]:
                p("Notiz: " + i["note"], 9, (67, 90, 150), "I")
            if i["url"].startswith(("http://", "https://")):
                pdf.set_font("Helvetica", "U", 8)
                pdf.set_text_color(42, 98, 212)
                pdf.multi_cell(0, 4.5, l1(i["url"]), link=i["url"], new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(221, 226, 234)
            pdf.set_line_width(0.2)
            pdf.line(15, pdf.get_y() + 1.5, 195, pdf.get_y() + 1.5)
            pdf.ln(2)
    if rep["notes"]:
        h("Notizen")
        for n in rep["notes"]:
            p(n["text"], 9)
            p(n["created_at"], 8, (120, 128, 145))
            pdf.ln(1)
    h("Quellenverzeichnis")
    for n, s in enumerate((s for s in rep["sources"] if s["url"].startswith(("http://", "https://"))), 1):
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(40, 46, 60)
        pdf.multi_cell(0, 4.5, l1(f"[{n}] {s['title'][:90]} ({s['domain']}) - Abruf {s['retrieved_at']}, Vertrauen {s['trust']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "U", 8)
        pdf.set_text_color(42, 98, 212)
        pdf.multi_cell(0, 4.5, l1(s["url"]), link=s["url"], new_x="LMARGIN", new_y="NEXT")
    h("Hinweise zur Datenqualitaet")
    for q in rep["quality"]:
        p("- " + q, 9)
    pdf.ln(3)
    p(rep["generator"], 8, (120, 128, 145))
    return bytes(pdf.output())


def filename(title: str, ext: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title).strip("-")[:50] or "bericht"
    return f"mosi-intel-{slug}.{ext}"
