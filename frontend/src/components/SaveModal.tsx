import { useEffect, useState } from "react";
import { api, Project, Source } from "../api";
import { Alert, Modal, Spinner } from "./ui";

export default function SaveModal({ source, category, kind, onClose, onSaved }: { source: Source; category?: string; kind: "web" | "name" | "image"; onClose: () => void; onSaved: () => void }) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [cats, setCats] = useState<string[]>([]);
  const [pid, setPid] = useState<string>("");
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState(category || "Allgemein");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api<Project[]>("/research"), api<string[]>("/research/categories")]).then(([p, c]) => { setProjects(p); setCats(c); setPid(p[0] ? String(p[0].id) : "new"); }).catch((e) => setErr(e.message));
  }, []);

  async function save() {
    setBusy(true); setErr("");
    try {
      let id = Number(pid);
      if (pid === "new") id = (await api<Project>("/research", { body: { title: title.trim() || "Neue Recherche" } })).id;
      await api(`/research/${id}/items`, { body: {
        type: kind, title: source.title, summary: source.summary || "", url: source.url, source_domain: source.domain, published: source.published || null,
        retrieved_at: source.retrieved_at, trust_level: source.trust.level, trust_score: source.trust.score, match: source.match || "", category: cat,
      } });
      onSaved();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <Modal title="In Rechercheprojekt speichern" onClose={onClose}>
      {!projects && !err ? <Spinner /> : (
        <div className="space-y-4">
          {err && <Alert kind="error">{err}</Alert>}
          <div>
            <label className="label" htmlFor="sp">Projekt</label>
            <select id="sp" className="input" value={pid} onChange={(e) => setPid(e.target.value)}>
              {projects?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              <option value="new">+ Neues Projekt anlegen…</option>
            </select>
          </div>
          {pid === "new" && <div><label className="label" htmlFor="sn">Projektname</label><input id="sn" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="z. B. Selbstauskunft 2025" autoFocus /></div>}
          <div>
            <label className="label" htmlFor="sc">Kategorie</label>
            <select id="sc" className="input" value={cat} onChange={(e) => setCat(e.target.value)}>{cats.map((c) => <option key={c}>{c}</option>)}</select>
          </div>
          <button className="btn btn-primary w-full" disabled={busy || !pid} onClick={save}>{busy ? "Speichert…" : "Speichern"}</button>
        </div>
      )}
    </Modal>
  );
}
