import { Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, download, fmtDate, Project } from "../api";
import { Alert, Empty, PageHeader, Spinner } from "../components/ui";

export default function Reports() {
  const [list, setList] = useState<Project[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => { Promise.all([api<Project[]>("/research"), api<Project[]>("/research?archived=true")]).then(([a, b]) => setList([...a, ...b])).catch((e) => setErr(e.message)); }, []);
  async function exp(id: number, f: string) { setBusy(`${id}${f}`); setErr(""); try { await download(id, f); } catch (e: any) { setErr(e.message); } finally { setBusy(""); } }
  return (
    <>
      <PageHeader title="Reports" sub="Exportiere Rechercheprojekte als PDF, HTML oder JSON – inklusive Quellen, Links und Hinweisen zur Datenqualität." />
      {err && <div className="mb-4"><Alert kind="error">{err}</Alert></div>}
      {!list ? <Spinner /> : list.length === 0 ? <div className="card"><Empty icon={<FileText size={28} />} title="Keine Projekte für Berichte" text="Lege zuerst unter Saved Researches ein Projekt an." /></div> :
        <div className="card divide-y divide-line">{list.map((p) => (
          <div key={p.id} className="p-4 flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1"><Link to={`/saved/${p.id}`} className="font-medium hover:text-accent truncate block">{p.title}{p.archived ? <span className="chip ml-2">archiviert</span> : null}</Link><div className="text-xs text-mute mt-0.5">{p.item_count} Quellen · {p.note_count} Notizen · {fmtDate(p.updated_at)}</div></div>
            <div className="flex gap-2">{["pdf", "html", "json"].map((f) => <button key={f} className="btn btn-sm uppercase" disabled={!!busy} onClick={() => exp(p.id, f)}><Download size={13} />{busy === `${p.id}${f}` ? "…" : f}</button>)}</div>
          </div>))}</div>}
    </>
  );
}
