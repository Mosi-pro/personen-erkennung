import { Archive, ArchiveRestore, ArrowLeft, Download, ExternalLink, FolderPlus, NotebookPen, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, download, fmtDate, Item, Project } from "../api";
import { Alert, Empty, MatchBadge, Modal, PageHeader, Spinner, TrustBadge } from "../components/ui";

function NewProject({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Project) => void }) {
  const [t, setT] = useState(""); const [d, setD] = useState(""); const [err, setErr] = useState("");
  return (
    <Modal title="Neues Rechercheprojekt" onClose={onClose}>
      <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); try { onCreated(await api("/research", { body: { title: t, description: d } })); } catch (x: any) { setErr(x.message); } }}>
        {err && <Alert kind="error">{err}</Alert>}
        <div><label className="label" htmlFor="pt">Name</label><input id="pt" className="input" value={t} onChange={(e) => setT(e.target.value)} required maxLength={150} autoFocus /></div>
        <div><label className="label" htmlFor="pd">Beschreibung</label><textarea id="pd" className="input" rows={3} value={d} onChange={(e) => setD(e.target.value)} maxLength={2000} /></div>
        <button className="btn btn-primary w-full">Anlegen</button>
      </form>
    </Modal>
  );
}

function List() {
  const [archived, setArchived] = useState(false);
  const [list, setList] = useState<Project[] | null>(null);
  const [err, setErr] = useState("");
  const [creating, setCreating] = useState(false);
  const nav = useNavigate();
  useEffect(() => { setList(null); api<Project[]>(`/research?archived=${archived}`).then(setList).catch((e) => setErr(e.message)); }, [archived]);
  return (
    <>
      <PageHeader title="Saved Researches" sub="Deine lokal gespeicherten Rechercheprojekte." actions={<button className="btn btn-primary" onClick={() => setCreating(true)}><Plus size={14} />Neues Projekt</button>} />
      <div className="flex gap-1 mb-4">{[[false, "Aktiv"], [true, "Archiviert"]].map(([v, l]) => <button key={String(v)} className={`btn btn-sm ${archived === v ? "border-accent text-accent" : ""}`} onClick={() => setArchived(v as boolean)}>{l as string}</button>)}</div>
      {err && <Alert kind="error">{err}</Alert>}
      {!list ? <Spinner /> : list.length === 0 ? <div className="card"><Empty icon={<FolderPlus size={28} />} title={archived ? "Keine archivierten Projekte" : "Noch keine Projekte"} text="Lege ein Projekt an oder speichere Ergebnisse direkt aus einer Suche." /></div> :
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{list.map((p) => <Link key={p.id} to={`/saved/${p.id}`} className="card p-4 hover:border-accent/60 transition-colors"><div className="font-medium truncate">{p.title}</div><div className="text-xs text-mute mt-1 line-clamp-2 min-h-8">{p.description || "Keine Beschreibung"}</div><div className="flex justify-between text-xs text-mute mt-3 pt-3 border-t border-line"><span>{p.item_count} Quellen · {p.note_count} Notizen</span><span>{fmtDate(p.updated_at)}</span></div></Link>)}</div>}
      {creating && <NewProject onClose={() => setCreating(false)} onCreated={(p) => nav(`/saved/${p.id}`)} />}
    </>
  );
}

function Detail({ id }: { id: number }) {
  const [p, setP] = useState<(Project & { items: Item[]; notes: { id: number; text: string; created_at: number }[] }) | null>(null);
  const [cats, setCats] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [filter, setFilter] = useState("Alle");
  const nav = useNavigate();
  const load = useCallback(() => api(`/research/${id}`).then(setP).catch((e) => setErr(e.message)), [id]);
  useEffect(() => { load(); api<string[]>("/research/categories").then(setCats); }, [load]);
  const act = (fn: () => Promise<unknown>) => fn().then(load).catch((e) => setErr(e.message));

  if (err && !p) return <Alert kind="error">{err}</Alert>;
  if (!p) return <Spinner />;
  const used = ["Alle", ...Array.from(new Set(p.items.map((i) => i.category)))];
  const items = p.items.filter((i) => filter === "Alle" || i.category === filter);
  return (
    <>
      <Link to="/saved" className="text-xs text-mute hover:text-ink flex items-center gap-1 mb-3"><ArrowLeft size={13} />Alle Projekte</Link>
      <PageHeader title={p.title} sub={p.description} actions={
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-sm" onClick={() => { const t = prompt("Neuer Projektname", p.title); if (t?.trim()) act(() => api(`/research/${id}`, { method: "PATCH", body: { title: t } })); }}>Umbenennen</button>
          <button className="btn btn-sm" onClick={() => act(() => api(`/research/${id}`, { method: "PATCH", body: { archived: !p.archived } }))}>{p.archived ? <><ArchiveRestore size={13} />Wiederherstellen</> : <><Archive size={13} />Archivieren</>}</button>
          <button className="btn btn-sm btn-danger" onClick={() => confirm(`Projekt „${p.title}“ mit allen Ergebnissen und Notizen endgültig löschen?`) && api(`/research/${id}`, { method: "DELETE" }).then(() => nav("/saved"))}><Trash2 size={13} />Löschen</button>
        </div>} />
      {err && <div className="mb-4"><Alert kind="error">{err}</Alert></div>}
      <div className="grid lg:grid-cols-3 gap-4">
        <section className="lg:col-span-2 space-y-3 min-w-0">
          <div className="flex flex-wrap gap-1">{used.map((c) => <button key={c} onClick={() => setFilter(c)} className={`btn btn-sm ${filter === c ? "border-accent text-accent" : ""}`}>{c}</button>)}</div>
          {items.length === 0 ? <div className="card"><Empty icon={<FolderPlus size={28} />} title="Keine Ergebnisse" text="Speichere Quellen über die Schaltfläche „In Projekt speichern“ in den Suchmodulen." /></div> :
            items.map((i) => (
              <article key={i.id} className="card p-4">
                <div className="text-xs text-mute font-mono mb-1">{i.source_domain}</div>
                <a href={i.url} target="_blank" rel="noopener noreferrer nofollow" className="font-medium hover:text-accent break-words">{i.title}</a>
                {i.summary && <p className="text-sm text-mute mt-1.5">{i.summary}</p>}
                <div className="flex flex-wrap gap-1.5 mt-2.5"><TrustBadge trust={{ level: i.trust_level, score: i.trust_score }} /><MatchBadge match={i.match} />{i.published && <span className="chip">Veröffentlicht: {i.published}</span>}<span className="chip">Abruf: {i.retrieved_at}</span></div>
                <div className="mt-3 pt-3 border-t border-line grid sm:grid-cols-[180px_1fr_auto] gap-2 items-start">
                  <select className="input py-1.5 text-xs" value={i.category} aria-label="Kategorie" onChange={(e) => act(() => api(`/research/${id}/items/${i.id}`, { method: "PATCH", body: { category: e.target.value } }))}>{Array.from(new Set([...cats, i.category])).map((c) => <option key={c}>{c}</option>)}</select>
                  <input className="input py-1.5 text-xs" defaultValue={i.note} placeholder="Notiz zur Quelle…" aria-label="Notiz" maxLength={3000} onBlur={(e) => e.target.value !== i.note && act(() => api(`/research/${id}/items/${i.id}`, { method: "PATCH", body: { note: e.target.value } }))} />
                  <div className="flex gap-1.5"><a className="btn btn-sm px-2" href={i.url} target="_blank" rel="noopener noreferrer nofollow" aria-label="Originalquelle öffnen"><ExternalLink size={13} /></a>
                    <button className="btn btn-sm btn-danger px-2" aria-label="Ergebnis entfernen" onClick={() => act(() => api(`/research/${id}/items/${i.id}`, { method: "DELETE" }))}><Trash2 size={13} /></button></div>
                </div>
              </article>))}
        </section>
        <aside className="space-y-4 self-start">
          <section className="card"><div className="card-h"><NotebookPen size={14} />Notizen</div>
            <form className="p-3 border-b border-line space-y-2" onSubmit={(e) => { e.preventDefault(); if (note.trim()) act(() => api(`/research/${id}/notes`, { body: { text: note } }).then(() => setNote(""))); }}>
              <textarea className="input" rows={3} placeholder="Neue Notiz…" value={note} onChange={(e) => setNote(e.target.value)} maxLength={10000} aria-label="Neue Notiz" /><button className="btn btn-sm w-full" disabled={!note.trim()}>Notiz hinzufügen</button></form>
            {p.notes.length === 0 ? <div className="p-4 text-xs text-mute">Noch keine Notizen.</div> : <ul>{p.notes.map((n) => <li key={n.id} className="p-3 border-b border-line last:border-0 text-sm"><div className="whitespace-pre-wrap">{n.text}</div><div className="flex justify-between mt-1.5 text-[11px] text-mute">{fmtDate(n.created_at)}<button className="hover:text-bad" onClick={() => act(() => api(`/research/${id}/notes/${n.id}`, { method: "DELETE" }))} aria-label="Notiz löschen"><Trash2 size={12} /></button></div></li>)}</ul>}
          </section>
          <section className="card"><div className="card-h"><Download size={14} />Bericht exportieren</div><div className="p-3 flex gap-2">{["pdf", "html", "json"].map((f) => <button key={f} className="btn btn-sm flex-1 uppercase" onClick={() => download(id, f).catch((e) => setErr(e.message))}>{f}</button>)}</div></section>
        </aside>
      </div>
    </>
  );
}

export default function Saved() {
  const { id } = useParams();
  return id ? <Detail id={Number(id)} /> : <List />;
}
