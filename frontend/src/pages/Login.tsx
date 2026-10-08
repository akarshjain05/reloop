import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";
import { Button, Card, Field, inputCls, Notice, Tabs } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { homeFor, useAuth } from "../lib/auth";
import { useRuntime } from "../lib/runtime";
import { useAsync } from "../lib/useAsync";

const ROLE_LABEL: Record<string, string> = { USER: "Resident (Akarsh)", ORGANIZATION_ADMIN: "Campus admin", COLLECTOR: "Collector", ADMIN: "Platform admin" };

export default function Login() {
  const { user, login, register } = useAuth();
  const { status } = useRuntime();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [f, setF] = useState({ email: "", password: "", name: "", building_id: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const buildings = useAsync(() => api.get("/public/buildings"), []);
  useEffect(() => { if (user) nav(params.get("next") || homeFor(user), { replace: true }); }, [user, nav, params]);

  const run = async (fn: () => Promise<unknown>) => {
    setError(null); setBusy(true);
    try { await fn(); } catch (e) {
      const err = e as ApiError;
      setError(err.fields?.length ? err.fields.map((x) => `${x.field}: ${x.message}`).join(". ") : err.message);
    } finally { setBusy(false); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); run(() => (mode === "in" ? login(f.email, f.password) : register({ email: f.email, password: f.password, name: f.name, building_id: f.building_id || undefined }))); };
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-petrol-700 p-12 text-white lg:flex">
        <Link to="/" aria-label="ReLoop home"><Logo light /></Link>
        <div>
          <h1 className="text-5xl font-bold leading-tight">Turn waste<br />into value.</h1>
          <ul className="mt-6 max-w-md space-y-3 text-lg text-petrol-100">
            <li>Photograph an old device and see what it's worth.</li>
            <li>Get one clear next step: resell, repair, recycle or donate.</li>
            <li>Earn points after a verified pickup and watch your building's score move.</li>
          </ul>
        </div>
        <p className="text-sm text-petrol-200">Estimates are labeled as estimates. You confirm every item.</p>
      </div>
      <div className="flex items-center justify-center bg-mist-100 p-5 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-6 lg:hidden"><Link to="/" aria-label="ReLoop home"><Logo /></Link></div>
          <Tabs label="Sign in or create an account" value={mode} onChange={(m) => { setMode(m); setError(null); }} tabs={[{ id: "in", label: "Sign in" }, { id: "up", label: "Create account" }]} />
          <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
            {mode === "up" && <Field label="Your name"><input className={inputCls} value={f.name} onChange={set("name")} autoComplete="name" required maxLength={60} /></Field>}
            <Field label="Email"><input className={inputCls} type="email" value={f.email} onChange={set("email")} autoComplete="email" required /></Field>
            <Field label="Password" hint={mode === "up" ? "At least 8 characters." : undefined}><input className={inputCls} type="password" value={f.password} onChange={set("password")} autoComplete={mode === "in" ? "current-password" : "new-password"} required /></Field>
            {mode === "up" && (
              <Field label="Your building"><select className={inputCls} value={f.building_id} onChange={set("building_id")}><option value="">Choose later</option>{buildings.data?.map((b: any) => <option key={b.id} value={b.id}>{b.name} ({b.neighborhood})</option>)}</select></Field>
            )}
            {error && <Notice tone="alert">{error}</Notice>}
            <Button type="submit" size="lg" className="w-full" loading={busy}>{mode === "in" ? "Sign in" : "Create account"}</Button>
          </form>

          {status && status.demo_accounts.length > 0 && (
            <Card className="mt-6" aria-label="Demo accounts">
              <h2 className="text-lg font-semibold">Try a demo account</h2>
              <p className="text-sm text-ink-500">Fictional data. Pick a role to explore the full loop.</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {status.demo_accounts.map((a) => <Button key={a.email} variant="outline" size="sm" disabled={busy} onClick={() => run(() => login(a.email, a.password))}>{ROLE_LABEL[a.role] ?? a.role}</Button>)}
              </div>
              <details className="mt-3 text-sm text-ink-500"><summary className="cursor-pointer font-medium text-ink-700">Show demo credentials</summary>
                <ul className="mt-2 space-y-1">{status.demo_accounts.map((a) => <li key={a.email}><code>{a.email}</code> / <code>{a.password}</code></li>)}</ul></details>
            </Card>
          )}
          {!status && <p className="mt-6 text-sm text-ink-500" role="status">Connecting to ReLoop…</p>}
        </div>
      </div>
    </div>
  );
}
