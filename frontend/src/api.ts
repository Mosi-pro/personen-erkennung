let csrf = "";
export const setCsrf = (t: string) => { csrf = t; };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const method = opts.method ?? (opts.body || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { "X-CSRF-Token": csrf };
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  let r: Response;
  try { r = await fetch("/api" + path, { method, headers, body, credentials: "same-origin" }); }
  catch { throw new ApiError(0, "Server nicht erreichbar."); }
  if (!r.ok) {
    let msg = `Fehler ${r.status}`;
    try { const j = await r.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* ignore */ }
    throw new ApiError(r.status, msg);
  }
  return r.json();
}

export async function download(project_id: number, format: string): Promise<void> {
  const r = await fetch("/api/reports/export", {
    method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify({ project_id, format }),
  });
  if (!r.ok) { let m = "Export fehlgeschlagen."; try { m = (await r.json()).detail || m; } catch { /* */ } throw new ApiError(r.status, m); }
  const cd = r.headers.get("content-disposition") || "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] || `bericht.${format}`;
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export type Trust = { level: "high" | "medium" | "low" | "unknown"; score: number; label: string };
export type Match = "" | "confirmed" | "name_only" | "unconfirmed";
export interface Source {
  title: string; url: string; summary: string; domain: string; published?: string | null; retrieved_at: string;
  trust: Trust; match?: Match; category?: string; type?: "web" | "name" | "image"; thumbnail?: string | null; data?: Record<string, unknown>;
}
export interface Project { id: number; title: string; description: string; archived: number; created_at: number; updated_at: number; item_count?: number; note_count?: number }
export interface Item {
  id: number; project_id: number; type: string; title: string; summary: string; url: string; source_domain: string; published: string | null;
  retrieved_at: string; trust_level: Trust["level"]; trust_score: number; match: Match; category: string; note: string;
}
export const fmtDate = (t: number) => new Date(t * 1000).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
