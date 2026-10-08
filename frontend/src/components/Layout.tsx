import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Bell, Building2, ClipboardCheck, Cloud, Flag, Home, Leaf, LogOut, MapPin, Menu, ScanLine, Sparkles, Store, Trophy, Truck, X } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn, timeAgo } from "../lib/format";
import { useRuntime } from "../lib/runtime";
import { Logo } from "./Logo";
import { Badge } from "./ui";

const NAV = [
  { to: "/dashboard", label: "Home", icon: Home },
  { to: "/scan", label: "Scan", icon: ScanLine },
  { to: "/exchange", label: "Exchange", icon: Store },
  { to: "/recyclers", label: "Find a recycler", icon: MapPin },
  { to: "/pickup", label: "Pickups", icon: Truck },
  { to: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { to: "/challenges", label: "Challenges", icon: Flag },
  { to: "/impact", label: "My impact", icon: Leaf },
  { to: "/advisor", label: "Advisor", icon: Sparkles },
  { to: "/org", label: "Building and campus", icon: Building2 },
  { to: "/ops", label: "Operations", icon: ClipboardCheck, roles: ["ADMIN", "COLLECTOR"] },
];

function RuntimeBadge() {
  const { status, offline, setOpen } = useRuntime();
  const live = status?.on_aws;
  return (
    <button onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label="Show runtime and AWS details"
      className="inline-flex h-9 items-center gap-2 rounded-full border border-mist-300 bg-white px-3 text-sm font-medium text-ink-700 hover:bg-mist-50">
      <span className={cn("h-2 w-2 rounded-full", offline ? "bg-alert" : live ? "bg-ok" : "bg-signal")} aria-hidden="true" />
      {offline ? "API offline" : live ? "Running on AWS" : "Demo mode"}
    </button>
  );
}

function AwsProofDrawer() {
  const { status, proof, open, setOpen } = useRuntime();
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, setOpen]);
  if (!open) return null;
  const r = status?.runtime;
  const row = (k: string, v: unknown) => (
    <div key={k} className="flex justify-between gap-4 border-b border-mist-200 py-2 text-sm"><dt className="text-ink-500">{k}</dt><dd className="break-all text-right font-medium">{String(v ?? "none")}</dd></div>
  );
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/40" onClick={() => setOpen(false)}>
      <aside role="dialog" aria-modal="true" aria-label="Runtime and AWS details" onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl animate-pop">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-xl font-semibold"><Cloud className="h-5 w-5 text-petrol-600" aria-hidden="true" />Under the hood</h2>
          <button ref={closeRef} onClick={() => setOpen(false)} aria-label="Close" className="grid h-10 w-10 place-items-center rounded-lg hover:bg-mist-200"><X className="h-5 w-5" /></button>
        </div>
        <p className="mb-4 rounded-xl bg-mist-100 p-3 text-sm text-ink-700">{status?.banner ?? "Checking the backend…"}</p>
        {r && (
          <dl>
            <h3 className="mt-2 text-sm font-semibold text-ink-500">This deployment</h3>
            {row("AI provider", r.ai === "bedrock" ? "Amazon Bedrock" : "Demo mock (not computer vision)")}
            {row("Model", r.model_id)}{row("Bedrock region", r.bedrock_region)}
            {row("Agent", r.agent === "strands" ? "Strands Agents SDK" : "Fixed tool pipeline")}
            {row("Database", r.store === "dynamodb" ? `DynamoDB (${r.table})` : "In-memory demo store")}
            {row("Image storage", r.storage === "s3" ? `S3 (${r.bucket})` : "Local disk")}
            {row("Sign-in", r.auth === "cognito" ? "Amazon Cognito" : "Dev auth")}
            {row("API region", r.region)}{row("Running in Lambda", r.in_lambda ? "yes" : "no")}
          </dl>
        )}
        {proof && (
          <dl className="mt-6">
            <h3 className="text-sm font-semibold text-ink-500">Your last scan</h3>
            {row("Classified by", `${proof.ai_provider} (${proof.model_id})`)}{row("Agent mode", proof.agent_mode)}
            {row("Saved to", `${proof.store}${proof.table ? ` / ${proof.table}` : ""}`)}
            {row("Image object", proof.bucket ? `s3://${proof.bucket}/${proof.object_key}` : "local disk")}
            {row("Lambda request id", proof.lambda_request_id)}{row("Total time", `${proof.total_ms} ms`)}
          </dl>
        )}
        <p className="mt-6 text-xs text-ink-500">Values come straight from the API response, so what you see here matches what CloudWatch, S3 and DynamoDB show in the AWS console.</p>
      </aside>
    </div>
  );
}

function Bell_() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<{ unread: number; items: any[] }>({ unread: 0, items: [] });
  const loc = useLocation();
  useEffect(() => { api.get("/notifications").then(setData, () => {}); }, [loc.pathname, loc.search]);
  const toggle = () => {
    setOpen((o) => !o);
    if (!open && data.unread) api.post("/notifications/read").then(() => setData((d) => ({ ...d, unread: 0 })), () => {});
  };
  return (
    <div className="relative">
      <button onClick={toggle} aria-label={`Notifications${data.unread ? `, ${data.unread} unread` : ""}`} aria-expanded={open} className="relative grid h-10 w-10 place-items-center rounded-full hover:bg-mist-200">
        <Bell className="h-5 w-5" aria-hidden="true" />
        {data.unread > 0 && <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-signal px-1 text-[10px] font-bold text-ink">{data.unread}</span>}
      </button>
      {open && (
        <div role="region" aria-label="Notifications" className="absolute right-0 z-40 mt-2 w-80 max-w-[85vw] rounded-2xl border border-mist-200 bg-white p-2 shadow-xl animate-pop">
          {data.items.length === 0 ? <p className="p-4 text-sm text-ink-500">Nothing yet. Updates about your pickups and points land here.</p> : (
            <ul className="max-h-96 overflow-y-auto">
              {data.items.slice(0, 12).map((n) => (
                <li key={n.id} className="rounded-xl px-3 py-2 hover:bg-mist-50"><div className="text-sm font-medium">{n.title}</div>{n.body && <div className="text-sm text-ink-500">{n.body}</div>}<div className="text-xs text-ink-400">{timeAgo(n.created_at)}</div></li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

const linkCls = ({ isActive }: { isActive: boolean }) =>
  cn("flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition-colors", isActive ? "bg-petrol-50 text-petrol-700" : "text-ink-700 hover:bg-mist-100");

export default function Layout() {
  const { user, logout } = useAuth();
  const [more, setMore] = useState(false);
  const loc = useLocation();
  useEffect(() => setMore(false), [loc.pathname]);
  const items = NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role)));
  const bottom = [{ to: "/dashboard", label: "Home", icon: Home }, { to: "/exchange", label: "Exchange", icon: Store }, { to: "/scan", label: "Scan", icon: ScanLine, center: true },
    { to: "/leaderboard", label: "Rank", icon: Trophy }];
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[250px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2">Skip to content</a>
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-mist-200 bg-white px-4 py-6 lg:flex">
        <div className="px-3"><Logo /></div>
        <nav aria-label="Main" className="mt-8 flex-1 space-y-1 overflow-y-auto">
          {items.map((n) => <NavLink key={n.to} to={n.to} className={linkCls}><n.icon className="h-5 w-5" aria-hidden="true" />{n.label}</NavLink>)}
        </nav>
        <div className="mt-4 rounded-xl bg-mist-100 p-3">
          <div className="truncate text-sm font-semibold">{user?.name}</div>
          <Badge tone="petrol" className="mt-1">{user?.role.replace("_", " ").toLowerCase()}</Badge>
          <button onClick={logout} className="mt-3 flex h-9 w-full items-center gap-2 rounded-lg text-sm text-ink-700 hover:bg-mist-200"><LogOut className="h-4 w-4" aria-hidden="true" />Sign out</button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-col pb-28 lg:pb-0">
        <header className="pt-safe sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-mist-200 bg-mist-100/90 px-4 py-3 backdrop-blur lg:px-8">
          <div className="lg:hidden"><Logo /></div>
          <div className="ml-auto flex items-center gap-2"><RuntimeBadge /><Bell_ /></div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 py-6 lg:px-8 lg:py-8"><Outlet /></main>
      </div>

      <nav aria-label="Primary" className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-mist-200 bg-white/95 backdrop-blur lg:hidden">
        <ul className="mx-auto flex max-w-md items-end justify-around px-2 pt-1">
          {bottom.map((n) => (
            <li key={n.to} className="flex-1">
              <NavLink to={n.to} aria-label={n.label} className={({ isActive }) => cn("flex flex-col items-center gap-0.5 py-2 text-xs font-medium", isActive ? "text-petrol-700" : "text-ink-500")}>
                {n.center ? <span className="-mt-7 grid h-14 w-14 place-items-center rounded-full bg-signal text-ink shadow-lg ring-4 ring-white"><n.icon className="h-6 w-6" aria-hidden="true" /></span> : <n.icon className="h-6 w-6" aria-hidden="true" />}
                {n.label}
              </NavLink>
            </li>
          ))}
          <li className="flex-1"><button onClick={() => setMore(true)} aria-label="More" className="flex w-full flex-col items-center gap-0.5 py-2 text-xs font-medium text-ink-500"><Menu className="h-6 w-6" aria-hidden="true" />More</button></li>
        </ul>
      </nav>
      {more && (
        <div className="fixed inset-0 z-50 flex items-end bg-ink/40 lg:hidden" onClick={() => setMore(false)}>
          <div role="dialog" aria-modal="true" aria-label="More" className="pb-safe w-full rounded-t-3xl bg-white p-4 animate-pop" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between px-2"><span className="font-display text-lg font-semibold">{user?.name}</span><button onClick={() => setMore(false)} aria-label="Close" className="grid h-10 w-10 place-items-center rounded-lg hover:bg-mist-200"><X className="h-5 w-5" /></button></div>
            <div className="grid grid-cols-2 gap-1">
              {items.filter((n) => !bottom.some((b) => b.to === n.to)).map((n) => <NavLink key={n.to} to={n.to} className={linkCls}><n.icon className="h-5 w-5" aria-hidden="true" />{n.label}</NavLink>)}
              <button onClick={logout} className="flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] font-medium text-ink-700 hover:bg-mist-100"><LogOut className="h-5 w-5" aria-hidden="true" />Sign out</button>
            </div>
          </div>
        </div>
      )}
      <AwsProofDrawer />
    </div>
  );
}
