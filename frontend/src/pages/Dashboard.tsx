import { Bookmark, Globe, Image as ImageIcon, UserSearch } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate } from "../api";
import { Alert, Empty, PageHeader, Spinner, TrustBadge } from "../components/ui";

const KIND: Record<string, [string, string]> = { name: ["Name", "/name"], web: ["Web", "/web"], image: ["Bild", "/image"] };

function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return <div className="card p-4"><div className="label mb-2">{label}</div><div className="text-2xl font-semibold tabular-nums">{value}</div>{sub && <div className="text-xs text-mute mt-1">{sub}</div>}</div>;
}

export default function Dashboard() {
  const [d, setD] = useState<any>(null);
  const [st, setSt] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/dashboard").then(setD).catch((e) => setErr(e.message)); api("/system/status").then(setSt).catch(() => {}); }, []);
  if (err) return <Alert kind="error">{err}</Alert>;
  if (!d) return <Spinner />;
  const w = d.stats.searches_week;
  return (
    <>
      <PageHeader title="Dashboard" sub="Übersicht deiner Recherchen, Quellen und des Systemzustands." />
      {st && !st.search_ready && <div className="mb-5"><Alert kind="warn">Es ist noch kein Suchanbieter konfiguriert. Trage unter <Link className="text-accent underline" to="/settings">Settings</Link> eine SearXNG-URL oder einen Brave-API-Schlüssel ein – bis dahin liefert nur Wikipedia Ergebnisse.</Alert></div>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Stat label="Aktive Projekte" value={d.stats.projects} sub={`${d.stats.archived} archiviert`} />
        <Stat label="Gespeicherte Quellen" value={d.stats.sources} />
        <Stat label="Suchen (7 Tage)" value={Object.values<number>(w).reduce((a, b) => a + b, 0)} sub={`Name ${w.name ?? 0} · Web ${w.web ?? 0} · Bild ${w.image ?? 0}`} />
        <Stat label="Suchen gesamt" value={d.stats.searches_total} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        {[["/name", UserSearch, "Name Research", "Wo taucht ein Name öffentlich auf?"], ["/web", Globe, "Web Intelligence", "Freie Suche, Filter, Quellensammlung"], ["/image", ImageIcon, "Image Research", "Bildmerkmale analysieren, Quellen finden"]].map(([to, I, t, s]: any) => (
          <Link key={to} to={to} className="card p-4 flex gap-3 hover:border-accent/60 transition-colors"><I size={20} className="text-accent shrink-0" /><div><div className="font-medium text-sm">{t}</div><div className="text-xs text-mute mt-0.5">{s}</div></div></Link>
        ))}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <section className="card"><div className="card-h"><Bookmark size={14} />Letzte Rechercheprojekte</div>
          {d.recent_projects.length === 0 ? <Empty icon={<Bookmark />} title="Noch keine Projekte" text="Speichere Ergebnisse aus einer Suche in einem neuen Projekt." /> :
            <ul>{d.recent_projects.map((p: any) => <li key={p.id} className="border-b border-line last:border-0"><Link to={`/saved/${p.id}`} className="flex justify-between gap-3 px-4 py-3 hover:bg-panel2"><span className="truncate text-sm">{p.title}</span><span className="text-xs text-mute shrink-0">{p.item_count} Quellen · {fmtDate(p.updated_at)}</span></Link></li>)}</ul>}
        </section>
        <section className="card"><div className="card-h">Letzte Suchen</div>
          {d.recent_searches.length === 0 ? <Empty icon={<Globe />} title="Noch keine Suchen" /> :
            <ul>{d.recent_searches.map((s: any) => <li key={s.id} className="border-b border-line last:border-0"><Link to={s.kind === "image" ? "/image" : `${KIND[s.kind][1]}?h=${s.id}`} className="flex justify-between gap-3 px-4 py-3 hover:bg-panel2"><span className="truncate text-sm"><span className="chip mr-2">{KIND[s.kind][0]}</span>{s.label}</span><span className="text-xs text-mute shrink-0">{s.result_count} · {fmtDate(s.created_at)}</span></Link></li>)}</ul>}
        </section>
        <section className="card"><div className="card-h">Zuletzt gefundene Quellen</div>
          {d.recent_sources.length === 0 ? <Empty icon={<Globe />} title="Noch keine gespeicherten Quellen" /> :
            <ul>{d.recent_sources.map((s: any) => <li key={s.id} className="px-4 py-3 border-b border-line last:border-0"><a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="text-sm hover:text-accent line-clamp-1">{s.title}</a><div className="flex items-center gap-2 mt-1 text-xs text-mute"><span className="font-mono">{s.source_domain}</span><TrustBadge trust={{ level: s.trust_level }} /><Link to={`/saved/${s.project_id}`} className="ml-auto hover:text-ink truncate">{s.project}</Link></div></li>)}</ul>}
        </section>
        <section className="card"><div className="card-h">Systemstatus</div>
          {!st ? <Spinner /> : <dl className="p-4 grid grid-cols-2 gap-y-3 text-sm">
            {([["Version", st.version], ["Datenbank", st.database.ok ? `OK · ${st.database.size_kb} KB` : "Fehler"], ["Arbeitsspeicher (Prozess)", st.memory_mb ? `${st.memory_mb} MB` : "–"],
              ["Freier Speicher", `${st.disk.free_gb} GB`], ["SearXNG", st.providers.searxng ? "konfiguriert" : "nicht konfiguriert"], ["Brave Search", st.providers.brave ? "konfiguriert" : "nicht konfiguriert"],
              ["Wikipedia", "aktiv"], ["Texterkennung (OCR)", st.ocr ? "verfügbar" : "nicht installiert"]] as [string, string][]).map(([k, v]) => <div key={k} className="contents"><dt className="text-mute">{k}</dt><dd className="text-right">{v}</dd></div>)}
          </dl>}
        </section>
      </div>
    </>
  );
}
