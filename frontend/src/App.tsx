import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api, setCsrf } from "./api";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import ImageResearch from "./pages/ImageResearch";
import Login from "./pages/Login";
import NameResearch from "./pages/NameResearch";
import Reports from "./pages/Reports";
import Saved from "./pages/Saved";
import Settings from "./pages/Settings";
import WebIntel from "./pages/WebIntel";

export default function App() {
  const [user, setUser] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    api<{ username: string; csrf: string }>("/auth/me").then((m) => { setCsrf(m.csrf); setUser(m.username); }).catch(() => setUser(null));
  }, []);

  if (user === undefined) return <div className="h-full grid place-items-center"><Spinner /></div>;
  if (user === null) return <Login onLogin={(u, c) => { setCsrf(c); setUser(u); }} />;

  return (
    <Layout user={user} onLogout={async () => { try { await api("/auth/logout", { method: "POST" }); } catch { /* */ } setUser(null); }}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/image" element={<ImageResearch />} />
        <Route path="/name" element={<NameResearch />} />
        <Route path="/web" element={<WebIntel />} />
        <Route path="/saved" element={<Saved />} />
        <Route path="/saved/:id" element={<Saved />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<Settings onPasswordChanged={() => setUser(null)} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
