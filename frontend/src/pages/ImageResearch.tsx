import { ImageUp, MapPin, ScanText, Search, ShieldAlert, X } from "lucide-react";
import { DragEvent, useRef, useState } from "react";
import { api, Source } from "../api";
import SourceCard from "../components/SourceCard";
import { Alert, Empty, PageHeader, Spinner } from "../components/ui";

const OK = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const MAX_MB = 10;

export default function ImageResearch() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [exif, setExif] = useState(false);
  const [save, setSave] = useState(false);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [r, setR] = useState<any>(null);
  const [terms, setTerms] = useState("");
  const [again, setAgain] = useState<any>(null);
  const input = useRef<HTMLInputElement>(null);

  function pick(f?: File | null) {
    setErr(""); setR(null); setAgain(null);
    if (!f) return;
    if (!OK.includes(f.type)) return setErr("Nicht unterstütztes Format. Erlaubt: JPEG, PNG, WebP, GIF.");
    if (f.size > MAX_MB * 1024 * 1024) return setErr(`Datei zu groß (max. ${MAX_MB} MB).`);
    if (preview) URL.revokeObjectURL(preview);
    setFile(f); setPreview(URL.createObjectURL(f));
  }
  const drop = (e: DragEvent) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); };

  async function analyze() {
    if (!file) return;
    setBusy(true); setErr(""); setR(null); setAgain(null);
    const fd = new FormData();
    fd.append("file", file); fd.append("include_exif", String(exif)); fd.append("save_image", String(save));
    try { const x = await api("/image-research", { form: fd }); setR(x); setTerms((x.search?.terms ?? x.analysis.terms ?? []).join(", ")); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  async function reSearch() {
    setBusy(true); setErr("");
    try { setAgain(await api(`/image-research/${r.id}/search`, { body: { terms: terms.split(",").map((t) => t.trim()).filter(Boolean) } })); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  const a = r?.analysis;
  const s = again ?? r?.search;
  const toSource = (i: any): Source => ({ title: i.title, url: i.url, summary: i.snippet || (i.similarity != null ? "" : ""), domain: i.domain, retrieved_at: new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC", trust: i.trust, thumbnail: i.thumbnail, type: "image" });

  return (
    <>
      <PageHeader title="Image Research" sub="Analysiert Bildinhalte lokal (Text, QR-Codes, Ort, Farben, Metadaten) und sucht öffentlich nach Bildern und Seiten mit denselben Inhalten." />
      <div className="mb-5"><Alert kind="info"><b>Keine Personenidentifizierung:</b> MOSI INTEL führt keine Gesichtserkennung durch und gleicht keine Gesichter ab. Zeigt ein Bild Personen, wird es nur lokal analysiert und nicht für eine Websuche verwendet.</Alert></div>
      <div className="grid lg:grid-cols-5 gap-4">
        <section className="card lg:col-span-2 p-4 space-y-4 self-start">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={drop} onClick={() => input.current?.click()} role="button" tabIndex={0}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()} aria-label="Bild auswählen"
            className={`border border-dashed rounded-md min-h-48 grid place-items-center cursor-pointer text-center p-4 transition-colors ${drag ? "border-accent bg-accent/5" : "border-line2 hover:border-accent/60"}`}>
            {preview ? <img src={preview} alt="Vorschau" className="max-h-64 rounded object-contain" /> : <div className="text-mute text-sm"><ImageUp className="mx-auto mb-3 text-dim" size={28} />Bild hierher ziehen oder klicken<div className="text-xs mt-1 text-dim">JPEG, PNG, WebP, GIF · max. {MAX_MB} MB</div></div>}
            <input ref={input} type="file" accept={OK.join(",")} hidden onChange={(e) => pick(e.target.files?.[0])} />
          </div>
          {file && <div className="flex items-center justify-between text-xs text-mute"><span className="truncate">{file.name} · {(file.size / 1024).toFixed(0)} KB</span><button className="hover:text-ink" onClick={() => { setFile(null); setPreview(""); setR(null); setAgain(null); }} aria-label="Bild entfernen"><X size={14} /></button></div>}
          <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" className="accent-accent" checked={exif} onChange={(e) => setExif(e.target.checked)} />EXIF-Metadaten anzeigen</label>
          <label className="flex items-start gap-2 text-sm cursor-pointer"><input type="checkbox" className="accent-accent mt-1" checked={save} onChange={(e) => setSave(e.target.checked)} /><span>Bild auf dem Server speichern<span className="block text-xs text-mute">Standard: Bild wird nach der Analyse verworfen.</span></span></label>
          <button className="btn btn-primary w-full" disabled={!file || busy} onClick={analyze}><Search size={14} />{busy ? "Analysiere…" : "Analysieren & suchen"}</button>
        </section>
        <div className="lg:col-span-3 space-y-4 min-w-0">
          {err && <Alert kind="error">{err}</Alert>}
          {busy && <Spinner label="Bild wird verarbeitet…" />}
          {!r && !busy && !err && <div className="card"><Empty icon={<ImageUp size={28} />} title="Noch keine Analyse" text="Lade ein Bild hoch, um Text, Orte und Fundstellen zu ermitteln." /></div>}
          {a && (
            <>
              {a.contains_people && <Alert kind="warn"><div className="flex items-center gap-2"><ShieldAlert size={15} /><b>Personen erkannt – keine Websuche.</b></div><div className="mt-1">{a.notes[0]}</div></Alert>}
              <section className="card"><div className="card-h">Bildanalyse</div>
                <dl className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <div><dt className="label">Format</dt><dd>{a.format}</dd></div><div><dt className="label">Größe</dt><dd>{a.width}×{a.height}</dd></div><div><dt className="label">Dateigröße</dt><dd>{a.size_kb} KB</dd></div>
                  <div><dt className="label">Farben</dt><dd className="flex gap-1">{a.colors.map((c: string) => <span key={c} title={c} className="w-5 h-5 rounded border border-line2" style={{ background: c }} />)}</dd></div>
                </dl>
                {!a.contains_people && <div className="px-4 pb-4 space-y-3 text-sm">
                  {a.ocr_text && <div><div className="label flex items-center gap-1"><ScanText size={12} />Erkannter Text</div><pre className="bg-bg border border-line rounded p-2 text-xs whitespace-pre-wrap max-h-32 overflow-auto font-mono">{a.ocr_text}</pre></div>}
                  {a.qr && <div><div className="label">QR-Code</div><code className="text-xs break-all">{a.qr}</code></div>}
                  {a.place && <div className="flex items-center gap-1.5"><MapPin size={14} className="text-accent" />Ort laut GPS: {a.place}</div>}
                  {a.image_saved && <div className="text-xs text-mute">Bild wurde auf dem Server gespeichert.</div>}
                </div>}
                {a.notes.filter((_: string, i: number) => !(a.contains_people && i === 0)).map((n: string) => <div key={n} className="px-4 pb-4"><Alert kind="info">{n}</Alert></div>)}
              </section>
              {a.exif !== null && <section className="card"><div className="card-h">EXIF-Metadaten</div>{Object.keys(a.exif).length === 0 ? <div className="p-4 text-sm text-mute">Keine EXIF-Daten im Bild enthalten.</div> :
                <dl className="p-4 grid sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs">{Object.entries<string>(a.exif).map(([k, v]) => <div key={k} className="flex justify-between gap-3 border-b border-line py-1"><dt className="text-mute">{k}</dt><dd className="font-mono truncate max-w-[60%]" title={v}>{v}</dd></div>)}</dl>}</section>}
              {!a.contains_people && (
                <section className="card"><div className="card-h">Suchbegriffe</div><div className="p-4 flex flex-col sm:flex-row gap-2">
                  <input className="input" value={terms} onChange={(e) => setTerms(e.target.value)} placeholder="Begriffe, kommagetrennt (max. 4)" aria-label="Suchbegriffe" />
                  <button className="btn btn-primary shrink-0" disabled={busy || !terms.trim()} onClick={reSearch}>Suchen</button></div></section>
              )}
              {s && (
                <>
                  {s.errors?.length > 0 && <Alert kind="warn">{s.errors.join(" | ")}</Alert>}
                  <section><h2 className="text-sm font-semibold mb-3">Ähnliche Bilder ({s.images.length})</h2>
                    {s.images.length === 0 ? <div className="card"><Empty icon={<Search />} title="Keine Bildtreffer" /></div> :
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">{s.images.map((i: any) => (
                        <a key={i.url} href={i.url} target="_blank" rel="noopener noreferrer nofollow" className="card overflow-hidden hover:border-accent/60 group">
                          <div className="aspect-square bg-bg grid place-items-center">{i.thumbnail ? <img src={i.thumbnail} alt={i.title} loading="lazy" referrerPolicy="no-referrer" className="w-full h-full object-cover" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} /> : <span className="text-xs text-dim">Keine Vorschau</span>}</div>
                          <div className="p-2.5"><div className="text-xs line-clamp-2 group-hover:text-accent">{i.title}</div><div className="flex justify-between mt-1.5 text-[11px] text-mute"><span className="font-mono truncate">{i.domain}</span>{i.similarity != null && <span className="text-accent shrink-0 ml-2">{i.similarity}%</span>}</div></div>
                        </a>))}</div>}
                  </section>
                  {s.pages.length > 0 && <section><h2 className="text-sm font-semibold mb-3">Relevante Fundstellen ({s.pages.length})</h2><div className="space-y-3">{s.pages.map((p: any) => <SourceCard key={p.url} s={toSource(p)} kind="image" category="Bild" />)}</div></section>}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
