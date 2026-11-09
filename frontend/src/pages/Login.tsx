import { Lock } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../api";
import { Alert } from "../components/ui";

export default function Login({ onLogin }: { onLogin: (u: string, csrf: string) => void }) {
  const [u, setU] = useState("admin");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { const r = await api<{ username: string; csrf: string }>("/auth/login", { body: { username: u, password: p } }); onLogin(r.username, r.csrf); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="h-full grid place-items-center p-4">
      <form onSubmit={submit} className="card w-full max-w-sm p-6 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="6" fill="#4388FF" /><path d="M6 23V9h3l7 9 7-9h3v14h-3V14l-7 9-7-9v9z" fill="#0B0D12" /></svg>
          <div><div className="font-semibold tracking-[0.18em]">MOSI INTEL</div><div className="text-xs text-mute">Self-hosted Research Platform</div></div>
        </div>
        {err && <Alert kind="error">{err}</Alert>}
        <div><label className="label" htmlFor="u">Benutzername</label><input id="u" className="input" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required /></div>
        <div><label className="label" htmlFor="p">Passwort</label><input id="p" type="password" className="input" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required autoFocus /></div>
        <button className="btn btn-primary w-full" disabled={busy}><Lock size={14} />{busy ? "Anmelden…" : "Anmelden"}</button>
      </form>
    </div>
  );
}
