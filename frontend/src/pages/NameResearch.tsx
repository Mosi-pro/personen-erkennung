import { AlertTriangle, ChevronDown, ChevronRight, Users } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Source } from "../api";
import SourceCard from "../components/SourceCard";
import { Alert, Empty, PageHeader, Spinner, TrustBadge } from "../components/ui";

const PURPOSES = [
  ["self", "Ich suche nach meinem eigenen Namen (Selbstauskunft)"],
  ["public_figure", "Öffentlich auftretende Person (Beruf, Amt, Medien)"],
  ["organization", "Unternehmen / Organisation"],
];
const CAT: Record<string, string> = { career: "Beruflich", activities: "Allgemein", organizations: "Organisation", publications: "Veröffentlichung", news: "Nachrichten", press: "Pressemitteilung", official: "Offiziell" };

const toSource = (i: any): Source => ({ title: i.title, url: i.url, summary: i.summary, domain: i.domain, published: i.published, retrieved_at: i.retrieved_at, trust: i.trust, match: i.match, type: "name" });

export default function NameResearch() {
  const [sp] = useSearchParams();
  const [f, setF] = useState({ name: "", context: "", organization: "", region: "", purpose: "self" });
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [r, setR] = useState<any>(null);
  const [tab, setTab] = useState("sections");
  const [showUnc, setShowUnc] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    const h = sp.get("h");
    if (h) api(`/searches/${h}`).then((x) => { setR(x); setOk(true); setF({ ...f, ...x.query }); }).catch((e) => setErr(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(""); setR(null);
    try { setR(await api("/name-research", { body: f })); setTab("sections"); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }

  const self = f.purpose === "self";
  return (
    <>
      <PageHeader title="Name Research" sub="Finde heraus, wo ein Name im öffentlichen Web auftaucht – zum Beispiel dein eigener. Jede Information wird mit Originalquelle, Abrufdatum und Vertrauensbewertung belegt." />
      <form onSubmit={run} className="card p-4 space-y-4 mb-6">
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="sm:col-span-2"><label className="label" htmlFor="nm">Name *</label><input id="nm" className="input" required minLength={2} maxLength={100} placeholder="Vor- und Nachname bzw. Organisationsname" value={f.name} onChange={set("name")} /></div>
          <div><label className="label" htmlFor="ct">Beruflicher Kontext</label><input id="ct" className="input" placeholder="z. B. Softwareentwickler, Politiker" value={f.context} onChange={set("context")} /></div>
          <div><label className="label" htmlFor="og">Unternehmen / Organisation</label><input id="og" className="input" placeholder="z. B. Beispiel GmbH" value={f.organization} onChange={set("organization")} /></div>
          <div className="sm:col-span-2"><label className="label" htmlFor="rg">Land / Region</label><input id="rg" className="input" placeholder="z. B. Deutschland, Hamburg" value={f.region} onChange={set("region")} /></div>
        </div>
        <fieldset><legend className="label">Zweck der Recherche *</legend>
          <div className="space-y-1.5">{PURPOSES.map(([v, l]) => <label key={v} className="flex items-center gap-2 text-sm cursor-pointer"><input type="radio" className="accent-accent" name="purpose" checked={f.purpose === v} onChange={() => setF({ ...f, purpose: v })} />{l}</label>)}</div>
        </fieldset>
        <label className="flex items-start gap-2 text-sm cursor-pointer text-mute"><input type="checkbox" className="accent-accent mt-1" checked={ok} onChange={(e) => setOk(e.target.checked)} />
          <span>Ich bestätige, dass ich nur öffentlich verfügbare Informationen zu mir selbst, einer öffentlich auftretenden Person oder einer Organisation recherchiere – nicht zu Privatpersonen, deren privaten Kontaktdaten oder Minderjährigen.</span></label>
        <div className="flex justify-end"><button className="btn btn-primary" disabled={busy || !ok || f.name.trim().length < 2}>{busy ? "Recherche läuft…" : "Recherche starten"}</button></div>
      </form>
      {err && <Alert kind="error">{err}</Alert>}
      {busy && <Spinner label="Öffentliche Quellen werden abgefragt…" />}
      {r && (
        <div className="space-y-5">
          {r.errors?.length > 0 && <Alert kind="warn">{r.errors.join(" | ")}</Alert>}
          {r.warnings?.map((w: string) => <Alert key={w} kind="warn">{w}</Alert>)}
          <section className="card"><div className="card-h">Kurzbeschreibung</div><div className="p-4 text-sm leading-relaxed text-mute">{r.summary}</div>
            <div className="px-4 pb-4 flex flex-wrap gap-2 text-xs"><span className="chip">{r.stats.total} Fundstellen</span><span className="chip">{r.stats.confirmed} mit bestätigtem Kontext</span><span className="chip">{r.stats.domains} Domains</span><span className="chip">Abruf: {r.retrieved_at}</span></div></section>
          {r.namesakes.length > 0 && <section className="card"><div className="card-h"><Users size={14} />Mögliche Personen mit diesem Namen (Wikipedia)</div>
            <ul className="p-4 grid sm:grid-cols-2 gap-2 text-sm">{r.namesakes.map((n: any) => <li key={n.url}><a className="text-accent hover:underline" href={n.url} target="_blank" rel="noopener noreferrer nofollow">{n.title}</a><div className="text-xs text-mute line-clamp-2">{n.hint}</div></li>)}</ul></section>}
          <div className="flex gap-1 border-b border-line">{[["sections", "Strukturierte Ergebnisse"], ["domains", self ? "Wo taucht dein Name auf?" : "Fundstellen nach Domain"], ["sources", "Quellenverzeichnis"]].map(([k, l]) =>
            <button key={k} onClick={() => setTab(k)} className={`px-3 py-2 text-sm border-b-2 -mb-px ${tab === k ? "border-accent text-ink" : "border-transparent text-mute hover:text-ink"}`}>{l}</button>)}</div>
          {tab === "sections" && (
            <div className="space-y-6">
              {Object.entries<any>(r.sections).map(([k, s]) => s.items.length > 0 && (
                <section key={k}><h2 className="text-sm font-semibold mb-3 flex items-center gap-2">{s.label}<span className="chip">{s.items.length}</span></h2><div className="space-y-3">{s.items.map((i: any) => <SourceCard key={i.url} s={toSource(i)} category={CAT[k]} kind="name" />)}</div></section>
              ))}
              {r.stats.total === 0 && <Empty icon={<AlertTriangle />} title="Keine belegbaren Treffer" text="Prüfe die Schreibweise oder lasse den Kontext weg." />}
              {r.unconfirmed.length > 0 && <section><button onClick={() => setShowUnc(!showUnc)} className="text-sm font-semibold flex items-center gap-1.5 text-warn">{showUnc ? <ChevronDown size={15} /> : <ChevronRight size={15} />}Unbestätigte Treffer – möglicherweise andere Personen ({r.unconfirmed.length})</button>
                {showUnc && <div className="space-y-3 mt-3">{r.unconfirmed.map((i: any) => <SourceCard key={i.url} s={toSource(i)} kind="name" />)}</div>}</section>}
            </div>
          )}
          {tab === "domains" && (
            <div className="card overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-mute border-b border-line"><th className="p-3 font-medium">Domain</th><th className="p-3 font-medium">Treffer</th><th className="p-3 font-medium">Vertrauen</th><th className="p-3 font-medium">Beispiel</th></tr></thead>
              <tbody>{r.domains.map((d: any) => <tr key={d.domain} className="border-b border-line last:border-0"><td className="p-3 font-mono text-xs">{d.domain}{d.broker && <span className="chip text-bad border-bad/40 ml-2">Datenbroker</span>}</td><td className="p-3 tabular-nums">{d.count}</td><td className="p-3"><TrustBadge trust={d.trust} /></td><td className="p-3 max-w-xs truncate"><a className="text-accent hover:underline" href={d.sample_url} target="_blank" rel="noopener noreferrer nofollow">{d.sample_url}</a></td></tr>)}</tbody></table></div>
          )}
          {tab === "sources" && (
            <ol className="card divide-y divide-line text-sm">{r.sources.map((s: any) => <li key={s.n} className="p-3 flex gap-3"><span className="text-dim tabular-nums w-6 shrink-0">{s.n}</span><div className="min-w-0"><div className="truncate">{s.title}</div><a className="text-accent text-xs hover:underline break-all" href={s.url} target="_blank" rel="noopener noreferrer nofollow">{s.url}</a><div className="text-xs text-mute mt-1">Abruf {s.retrieved_at}{s.published ? ` · veröffentlicht ${s.published}` : ""} · Vertrauen: {s.trust.label}</div></div></li>)}</ol>
          )}
        </div>
      )}
    </>
  );
}
