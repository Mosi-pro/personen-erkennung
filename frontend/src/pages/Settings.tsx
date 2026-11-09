import { CheckCircle2, KeyRound, Plug } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { Alert, PageHeader, Spinner } from "../components/ui";

export default function Settings({ onPasswordChanged }: { onPasswordChanged: () => void }) {
  const [s, setS] = useState<any>(null);
  const [st, setSt] = useState<any>(null);
  const [key, setKey] = useState("");
  const [msg, setMsg] = useState<{ k: "ok" | "error"; t: string } | null>(null);
  const [tests, setTests] = useState<Record<string, { ok: boolean; message: string } | "busy">>({});
  const [pw, setPw] = useState({ cur: "", n1: "", n2: "" });
  const [pwErr, setPwErr] = useState("");

  const load = () => { api("/settings").then(setS).catch((e) => setMsg({ k: "error", t: e.message })); api("/system/status").then(setSt).catch(() => {}); };
  useEffect(load, []);

  async function save(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    const body: any = { searxng_url: s.searxng_url, wiki_langs: s.wiki_langs, geocoding_enabled: s.geocoding_enabled, result_limit: Number(s.result_limit) };
    if (key !== "") body.brave_api_key = key;
    try { setS(await api("/settings", { method: "PUT", body })); setKey(""); setMsg({ k: "ok", t: "Einstellungen gespeichert." }); api("/system/status").then(setSt); } catch (x: any) { setMsg({ k: "error", t: x.message }); }
  }
  async function test(name: string) {
    setTests({ ...tests, [name]: "busy" });
    try { const r = await api(`/settings/test/${name}`, { method: "POST" }); setTests((t) => ({ ...t, [name]: r })); } catch (e: any) { setTests((t) => ({ ...t, [name]: { ok: false, message: e.message } })); }
  }
  async function changePw(e: FormEvent) {
    e.preventDefault(); setPwErr("");
    if (pw.n1 !== pw.n2) return setPwErr("Die neuen Passwörter stimmen nicht überein.");
    try { await api("/auth/password", { body: { current_password: pw.cur, new_password: pw.n1 } }); onPasswordChanged(); } catch (x: any) { setPwErr(x.message); }
  }
  if (!s) return <Spinner />;
  const T = ({ n }: { n: string }) => { const r = tests[n]; return <div className="flex flex-col items-start gap-1.5"><button type="button" className="btn btn-sm" disabled={r === "busy"} onClick={() => test(n)}><Plug size={13} />{r === "busy" ? "Teste…" : "Verbindung testen"}</button>
    {r && r !== "busy" && <span className={`text-xs ${r.ok ? "text-ok" : "text-bad"}`}>{r.message}</span>}</div>; };

  return (
    <>
      <PageHeader title="Settings" sub="Suchanbieter, Datenschutz und Konto. API-Schlüssel werden nur serverseitig gespeichert und nie an den Browser zurückgegeben." />
      <div className="grid lg:grid-cols-3 gap-4">
        <form onSubmit={save} className="card lg:col-span-2 p-4 space-y-5">
          {msg && <Alert kind={msg.k}>{msg.t}</Alert>}
          <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
            <div><label className="label" htmlFor="sx">SearXNG-URL</label><input id="sx" className="input font-mono" placeholder="http://searxng:8080" value={s.searxng_url} onChange={(e) => setS({ ...s, searxng_url: e.target.value })} /><p className="text-xs text-mute mt-1.5">Kostenlos, selbst gehostet (<code>docker compose --profile searxng up -d</code>). Das JSON-Format muss aktiviert sein – die mitgelieferte Konfiguration tut das.</p></div><T n="searxng" />
          </div>
          <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
            <div><label className="label" htmlFor="bk">Brave Search API-Schlüssel {s.brave_configured && <span className="text-ok normal-case tracking-normal ml-1"><CheckCircle2 size={11} className="inline" /> gesetzt ({s.brave_hint})</span>}</label>
              <input id="bk" type="password" autoComplete="off" className="input font-mono" placeholder={s.brave_configured ? "Leer lassen = unverändert" : "Schlüssel eingeben"} value={key} onChange={(e) => setKey(e.target.value)} />
              <p className="text-xs text-mute mt-1.5">Optional. Kostenloses Kontingent über brave.com/search/api. {s.brave_configured && <button type="button" className="underline hover:text-ink" onClick={() => api("/settings", { method: "PUT", body: { brave_api_key: "" } }).then(setS)}>Schlüssel entfernen</button>}</p></div><T n="brave" />
          </div>
          <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
            <div><label className="label" htmlFor="wl">Wikipedia-Sprachen</label><input id="wl" className="input font-mono" value={s.wiki_langs} onChange={(e) => setS({ ...s, wiki_langs: e.target.value })} /></div><T n="wikipedia" />
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label" htmlFor="rl">Ergebnisse pro Anfrage</label><input id="rl" type="number" min={5} max={30} className="input" value={s.result_limit} onChange={(e) => setS({ ...s, result_limit: e.target.value })} /></div>
            <label className="flex items-start gap-2 text-sm cursor-pointer sm:pt-6"><input type="checkbox" className="accent-accent mt-1" checked={s.geocoding_enabled} onChange={(e) => setS({ ...s, geocoding_enabled: e.target.checked })} /><span>GPS-Koordinaten aus Bildern in Ortsnamen auflösen<span className="block text-xs text-mute">Sendet Koordinaten an OpenStreetMap Nominatim. Standard: aus.</span></span></label>
          </div>
          <div className="flex justify-end"><button className="btn btn-primary">Speichern</button></div>
        </form>
        <div className="space-y-4 self-start">
          <section className="card"><div className="card-h">Systemstatus</div>{!st ? <Spinner /> : <dl className="p-4 space-y-2 text-sm">
            {([["Version", st.version], ["Laufzeit", `${Math.floor(st.uptime_s / 3600)} h ${Math.floor((st.uptime_s % 3600) / 60)} min`], ["RAM (Prozess)", st.memory_mb ? `${st.memory_mb} MB` : "–"], ["Datenbank", `${st.database.size_kb} KB`], ["Freier Speicher", `${st.disk.free_gb} / ${st.disk.total_gb} GB`], ["Upload-Limit", `${st.max_upload_mb} MB`], ["OCR (Tesseract)", st.ocr ? "verfügbar" : "nicht installiert"]] as [string, string][]).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-mute">{k}</dt><dd>{v}</dd></div>)}</dl>}</section>
          <form onSubmit={changePw} className="card"><div className="card-h"><KeyRound size={14} />Passwort ändern</div><div className="p-4 space-y-3">
            {pwErr && <Alert kind="error">{pwErr}</Alert>}
            <input type="password" className="input" placeholder="Aktuelles Passwort" autoComplete="current-password" value={pw.cur} onChange={(e) => setPw({ ...pw, cur: e.target.value })} required aria-label="Aktuelles Passwort" />
            <input type="password" className="input" placeholder="Neues Passwort (min. 10 Zeichen)" autoComplete="new-password" minLength={10} value={pw.n1} onChange={(e) => setPw({ ...pw, n1: e.target.value })} required aria-label="Neues Passwort" />
            <input type="password" className="input" placeholder="Neues Passwort wiederholen" autoComplete="new-password" value={pw.n2} onChange={(e) => setPw({ ...pw, n2: e.target.value })} required aria-label="Neues Passwort wiederholen" />
            <button className="btn w-full">Passwort ändern</button></div></form>
        </div>
      </div>
    </>
  );
}
