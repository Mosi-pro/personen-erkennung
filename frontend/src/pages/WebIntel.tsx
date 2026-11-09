import { Plus, Search, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Source } from "../api";
import { Alert, Empty, PageHeader, Spinner } from "../components/ui";
import SourceCard from "../components/SourceCard";

const toSource = (r: any): Source => ({ title: r.title, url: r.url, summary: r.snippet, domain: r.domain, published: r.published, retrieved_at: r.retrieved_at, trust: r.trust, thumbnail: r.thumbnail });

export default function WebIntel() {
  const [sp, setSp] = useSearchParams();
  const [queries, setQueries] = useState<string[]>([sp.get("q") || ""]);
  const [range, setRange] = useState("any");
  const [domains, setDomains] = useState("");
  const [exclude, setExclude] = useState("");
  const [news, setNews] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState<any>(null);
  const [filter, setFilter] = useState("all");

  async function run(e?: FormEvent) {
    e?.preventDefault();
    const qs = queries.map((q) => q.trim()).filter(Boolean);
    if (!qs.length) return;
    setBusy(true); setErr(""); setRes(null);
    const list = (s: string) => s.split(/[\s,]+/).filter(Boolean);
    try { setRes(await api("/web-search", { body: { queries: qs, time_range: range, domains: list(domains), exclude_domains: list(exclude), news } })); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  useEffect(() => {
    const h = sp.get("h");
    if (h) api(`/searches/${h}`).then((r) => { setRes(r); setQueries(r.label.split(" · ")); }).catch((e) => setErr(e.message));
    else if (sp.get("q")) { run(); setSp({}, { replace: true }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const results: any[] = (res?.results ?? []).filter((r: any) => filter === "all" || r.trust.level === filter);
  return (
    <>
      <PageHeader title="Web Intelligence" sub="Freie Websuche über deine konfigurierten Anbieter – mit Zeitraum- und Domainfilter, Duplikaterkennung und Quellenkarten." />
      <form onSubmit={run} className="card p-4 space-y-4 mb-6">
        <div>
          <label className="label">Suchbegriffe (bis zu 5 Anfragen)</label>
          <div className="space-y-2">
            {queries.map((q, i) => (
              <div key={i} className="flex gap-2">
                <input className="input" value={q} placeholder='z. B. "Beispiel GmbH" Insolvenz' maxLength={300} onChange={(e) => setQueries(queries.map((x, j) => (j === i ? e.target.value : x)))} aria-label={`Suchanfrage ${i + 1}`} />
                {queries.length > 1 && <button type="button" className="btn px-2.5" onClick={() => setQueries(queries.filter((_, j) => j !== i))} aria-label="Anfrage entfernen"><X size={14} /></button>}
              </div>
            ))}
          </div>
          {queries.length < 5 && <button type="button" className="btn btn-sm mt-2" onClick={() => setQueries([...queries, ""])}><Plus size={13} />Weitere Anfrage</button>}
        </div>
        <div className="grid sm:grid-cols-3 gap-3">
          <div><label className="label" htmlFor="tr">Zeitraum</label><select id="tr" className="input" value={range} onChange={(e) => setRange(e.target.value)}>
            <option value="any">Beliebig</option><option value="day">Letzte 24 Stunden</option><option value="week">Letzte Woche</option><option value="month">Letzter Monat</option><option value="year">Letztes Jahr</option></select></div>
          <div><label className="label" htmlFor="dm">Nur Domains</label><input id="dm" className="input" placeholder="spiegel.de, zeit.de" value={domains} onChange={(e) => setDomains(e.target.value)} /></div>
          <div><label className="label" htmlFor="ex">Domains ausschließen</label><input id="ex" className="input" placeholder="reddit.com" value={exclude} onChange={(e) => setExclude(e.target.value)} /></div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" className="accent-accent" checked={news} onChange={(e) => setNews(e.target.checked)} />Nachrichtenrecherche (News-Kategorie)</label>
          <button className="btn btn-primary" disabled={busy || !queries.some((q) => q.trim())}><Search size={14} />{busy ? "Suche läuft…" : "Suchen"}</button>
        </div>
      </form>
      {err && <Alert kind="error">{err}</Alert>}
      {busy && <Spinner label="Anbieter werden abgefragt…" />}
      {res && (
        <>
          {res.errors?.length > 0 && <div className="mb-4"><Alert kind="warn">Teilweise Fehler: {res.errors.join(" | ")}</Alert></div>}
          <div className="flex flex-wrap items-center gap-3 mb-4 text-sm">
            <span className="text-mute">{res.results.length} Ergebnisse{res.duplicates_removed ? ` · ${res.duplicates_removed} Duplikate entfernt` : ""}</span>
            <div className="ml-auto flex gap-1">{[["all", "Alle"], ["high", "Hohes Vertrauen"], ["medium", "Mittel"], ["low", "Niedrig"]].map(([k, l]) => <button key={k} onClick={() => setFilter(k)} className={`btn btn-sm ${filter === k ? "border-accent text-accent" : ""}`}>{l}</button>)}</div>
          </div>
          {results.length === 0 ? <Empty icon={<Search />} title="Keine Treffer" text="Passe Suchbegriffe oder Filter an." /> : <div className="space-y-3">{results.map((r) => <SourceCard key={r.url} s={toSource(r)} kind="web" />)}</div>}
        </>
      )}
    </>
  );
}
