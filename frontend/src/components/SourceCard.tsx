import { ExternalLink, FolderPlus } from "lucide-react";
import { useState } from "react";
import type { Source } from "../api";
import SaveModal from "./SaveModal";
import { MatchBadge, TrustBadge } from "./ui";

export default function SourceCard({ s, category, kind = "web", compact }: { s: Source; category?: string; kind?: "web" | "name" | "image"; compact?: boolean }) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  return (
    <article className="card p-4 hover:border-line2 transition-colors">
      <div className="flex gap-3">
        {s.thumbnail && <img src={s.thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" className="w-20 h-20 object-cover rounded border border-line shrink-0 hidden sm:block" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-mute mb-1"><span className="font-mono truncate">{s.domain}</span></div>
          <a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="font-medium text-[15px] leading-snug hover:text-accent break-words">{s.title}</a>
          {s.summary && !compact && <p className="text-sm text-mute mt-1.5 leading-relaxed">{s.summary}</p>}
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            <TrustBadge trust={s.trust} />
            <MatchBadge match={s.match} />
            {s.published && <span className="chip">Veröffentlicht: {s.published}</span>}
            <span className="chip">Abruf: {s.retrieved_at}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-line">
        <a className="btn btn-sm" href={s.url} target="_blank" rel="noopener noreferrer nofollow"><ExternalLink size={13} />Originalquelle</a>
        <button className="btn btn-sm" onClick={() => setSaving(true)}><FolderPlus size={13} />{saved ? "Gespeichert ✓" : "In Projekt speichern"}</button>
      </div>
      {saving && <SaveModal source={s} category={category} kind={kind} onClose={() => setSaving(false)} onSaved={() => { setSaved(true); setSaving(false); }} />}
    </article>
  );
}
