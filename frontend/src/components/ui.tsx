import { AlertTriangle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import { ReactNode, useEffect } from "react";
import type { Trust } from "../api";

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {sub && <p className="text-sm text-mute mt-1 max-w-2xl">{sub}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Alert({ kind = "info", children }: { kind?: "info" | "warn" | "error" | "ok"; children: ReactNode }) {
  const map = {
    info: ["border-accent/40 bg-accent/5 text-ink", <Info key="i" size={16} className="text-accent shrink-0 mt-0.5" />],
    warn: ["border-warn/40 bg-warn/5", <AlertTriangle key="i" size={16} className="text-warn shrink-0 mt-0.5" />],
    error: ["border-bad/40 bg-bad/5", <AlertTriangle key="i" size={16} className="text-bad shrink-0 mt-0.5" />],
    ok: ["border-ok/40 bg-ok/5", <CheckCircle2 key="i" size={16} className="text-ok shrink-0 mt-0.5" />],
  } as const;
  return <div role={kind === "error" ? "alert" : undefined} className={`flex gap-2.5 border rounded px-3 py-2.5 text-sm ${map[kind][0]}`}>{map[kind][1]}<div className="min-w-0">{children}</div></div>;
}

export function Spinner({ label }: { label?: string }) {
  return <div className="flex items-center gap-2 text-sm text-mute py-6 justify-center"><Loader2 size={16} className="animate-spin" />{label ?? "Lädt…"}</div>;
}

export function Empty({ icon, title, text }: { icon: ReactNode; title: string; text?: string }) {
  return <div className="text-center py-12 text-mute"><div className="flex justify-center mb-3 text-dim">{icon}</div><div className="text-sm text-ink">{title}</div>{text && <div className="text-xs mt-1 max-w-sm mx-auto">{text}</div>}</div>;
}

const TRUST = { high: "text-ok border-ok/40", medium: "text-warn border-warn/40", low: "text-bad border-bad/40", unknown: "text-mute border-line2" } as const;
const TRUST_TXT = { high: "Hoch", medium: "Mittel", low: "Niedrig", unknown: "Unbekannt" } as const;
export function TrustBadge({ trust }: { trust: Pick<Trust, "level"> & Partial<Trust> }) {
  return <span title={trust.label} className={`chip ${TRUST[trust.level]}`}><span className="w-1.5 h-1.5 rounded-full bg-current" />Vertrauen: {TRUST_TXT[trust.level]}{trust.score ? ` · ${trust.score}` : ""}</span>;
}

const MATCH = { confirmed: ["Kontext bestätigt", "text-ok border-ok/40"], name_only: ["Nur Name belegt", "text-mute border-line2"], unconfirmed: ["Unbestätigt – evtl. Namensvetter", "text-warn border-warn/40"] } as const;
export function MatchBadge({ match }: { match?: string }) {
  if (!match || !(match in MATCH)) return null;
  const [t, c] = MATCH[match as keyof typeof MATCH];
  return <span className={`chip ${c}`}>{t}</span>;
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-end sm:items-center justify-center p-0 sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className="card w-full sm:max-w-md max-h-[90vh] overflow-auto rounded-b-none sm:rounded-b-md">
        <div className="card-h justify-between"><span>{title}</span><button className="text-mute hover:text-ink" onClick={onClose} aria-label="Schließen"><X size={16} /></button></div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
