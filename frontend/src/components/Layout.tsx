import { Bookmark, FileText, Globe, Image as ImageIcon, LayoutDashboard, LogOut, Menu, Search, Settings as Cog, User, UserSearch, X } from "lucide-react";
import { ReactNode, useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/image", label: "Image Research", icon: ImageIcon },
  { to: "/name", label: "Name Research", icon: UserSearch },
  { to: "/web", label: "Web Intelligence", icon: Globe },
  { to: "/saved", label: "Saved Researches", icon: Bookmark },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Cog },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="6" fill="#4388FF" /><path d="M6 23V9h3l7 9 7-9h3v14h-3V14l-7 9-7-9v9z" fill="#0B0D12" /></svg>
      <div className="leading-none"><div className="font-semibold tracking-[0.16em] text-[13px]">MOSI</div><div className="text-[10px] tracking-[0.3em] text-accent mt-1">INTEL</div></div>
    </div>
  );
}

function Status() {
  const [s, setS] = useState<any>(null);
  const [fail, setFail] = useState(false);
  useEffect(() => {
    const load = () => api("/system/status").then((x) => { setS(x); setFail(false); }).catch(() => setFail(true));
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);
  const state = fail || (s && !s.database.ok) ? "bad" : s && !s.search_ready ? "warn" : "ok";
  const txt = { ok: "System bereit", warn: "Kein Suchanbieter", bad: "Störung" }[state];
  const c = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[state];
  return <NavLink to="/settings" title={s ? `RAM ${s.memory_mb ?? "?"} MB · DB ${s.database.size_kb} KB` : ""} className="hidden sm:flex items-center gap-2 text-xs text-mute hover:text-ink border border-line rounded px-2.5 py-1.5"><span className={`w-2 h-2 rounded-full ${c}`} />{txt}</NavLink>;
}

function GlobalSearch() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any>(null);
  const nav = useNavigate();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); return; }
    const t = setTimeout(() => api("/local-search?q=" + encodeURIComponent(q.trim())).then(setRes).catch(() => setRes(null)), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => { const h = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setRes(null); document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  const go = (to: string) => { setRes(null); setQ(""); nav(to); };
  return (
    <div ref={box} className="relative flex-1 max-w-xl">
      <form onSubmit={(e) => { e.preventDefault(); if (q.trim()) go("/web?q=" + encodeURIComponent(q.trim())); }}>
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
        <input className="input pl-9 py-1.5" placeholder="Global suchen – Enter startet Websuche" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Globale Suche" />
      </form>
      {res && (
        <div className="absolute left-0 right-0 top-full mt-1 card shadow-xl z-40 max-h-80 overflow-auto text-sm">
          {[...res.projects.map((p: any) => ({ k: "p" + p.id, t: p.title, s: "Projekt", to: "/saved/" + p.id })),
            ...res.items.map((i: any) => ({ k: "i" + i.id, t: i.title, s: i.source_domain || "Quelle", to: "/saved/" + i.project_id })),
            ...res.searches.map((x: any) => ({ k: "s" + x.id, t: x.label, s: "Suchverlauf: " + x.kind, to: x.kind === "name" ? "/name?h=" + x.id : x.kind === "web" ? "/web?h=" + x.id : "/image" }))]
            .map((r) => <button key={r.k} onClick={() => go(r.to)} className="w-full text-left px-3 py-2 hover:bg-panel2 border-b border-line last:border-0"><div className="truncate">{r.t}</div><div className="text-xs text-mute">{r.s}</div></button>)}
          <button onClick={() => go("/web?q=" + encodeURIComponent(q.trim()))} className="w-full text-left px-3 py-2 hover:bg-panel2 text-accent">Im Web suchen: „{q}“</button>
        </div>
      )}
    </div>
  );
}

export default function Layout({ user, onLogout, children }: { user: string; onLogout: () => void; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const nav = (
    <nav className="flex-1 py-4 px-3 space-y-0.5">
      {NAV.map(({ to, label, icon: I, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded text-sm border-l-2 ${isActive ? "bg-accent/10 text-ink border-accent" : "text-mute border-transparent hover:text-ink hover:bg-panel2"}`}>
          <I size={16} />{label}
        </NavLink>
      ))}
    </nav>
  );
  return (
    <div className="h-full flex">
      <aside className="hidden lg:flex w-60 shrink-0 flex-col bg-panel border-r border-line">
        <div className="h-14 px-5 flex items-center border-b border-line"><Logo /></div>
        {nav}
        <div className="p-4 text-[11px] text-dim border-t border-line">Nur öffentliche Quellen.<br />Keine Gesichtserkennung.</div>
      </aside>
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <aside className="w-64 bg-panel border-r border-line flex flex-col">
            <div className="h-14 px-5 flex items-center justify-between border-b border-line"><Logo /><button onClick={() => setOpen(false)} aria-label="Menü schließen"><X size={18} /></button></div>
            {nav}
          </aside>
          <div className="flex-1 bg-black/60" onClick={() => setOpen(false)} />
        </div>
      )}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-14 shrink-0 border-b border-line bg-panel/60 px-3 sm:px-6 flex items-center gap-3">
          <button className="lg:hidden btn btn-sm px-2" onClick={() => setOpen(true)} aria-label="Menü öffnen"><Menu size={16} /></button>
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-2">
            <Status />
            <NavLink to="/settings" className="btn btn-sm px-2" aria-label="Einstellungen"><Cog size={15} /></NavLink>
            <div className="flex items-center gap-2 border border-line rounded px-2 py-1 text-xs text-mute"><User size={14} /><span className="hidden sm:inline">{user}</span>
              <button onClick={onLogout} className="hover:text-ink ml-1" title="Abmelden" aria-label="Abmelden"><LogOut size={14} /></button></div>
          </div>
        </header>
        <main className="flex-1 overflow-auto"><div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-8">{children}</div></main>
      </div>
    </div>
  );
}
