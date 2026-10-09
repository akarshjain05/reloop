import { useState } from "react";
import { Badge, Button, Card, Empty, ErrorBox, Field, inputCls, Notice, PageHeader, PageSkeleton, ProgressBar, Stat, Tabs } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn, dateShort, inr, kg, num, pct, STATUS_TONE, timeAgo } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function PickupsTab() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useAsync(() => api.get(`/pickups${status ? `?status=${status}` : ""}`), [status]);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [weight, setWeight] = useState("");
  const [match, setMatch] = useState(true);
  const [msg, setMsg] = useState<{ tone: "ok" | "alert"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const move = async (id: string, body: any) => {
    setBusy(id); setMsg(null);
    try {
      const p = await api.patch(`/pickups/${id}/status`, body);
      if (p.rewards) setMsg({ tone: "ok", text: `Verified for ${p.user_name}: +${p.rewards.points} points${p.rewards.points_held ? " (held for review)" : ""}, ${kg(p.rewards.kg)} diverted. Rank ${p.rewards.rank_before} → ${p.rewards.rank_after}; building score ${p.rewards.building_score_before} → ${p.rewards.building_score_after}.` });
      setVerifying(null); setWeight(""); setMatch(true); reload();
    } catch (e) { setMsg({ tone: "alert", text: e instanceof ApiError ? e.message : "That didn't work." }); } finally { setBusy(null); }
  };
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="space-y-3">
      <label className="block max-w-xs"><span className="sr-only">Filter by status</span><select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All requests</option>{["requested", "scheduled", "collector_assigned", "picked_up", "verified", "recycled"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></label>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      {loading && !data ? <PageSkeleton /> : !data?.length ? <Empty title="No requests here" body="New pickup and drop-off requests appear in this queue." /> : (
        <ul className="space-y-3">{data.map((p: any) => (
          <li key={p.id}><Card>
            <div className="flex flex-wrap items-start justify-between gap-2"><div><div className="font-semibold">{p.items.map((i: any) => `${i.quantity > 1 ? i.quantity + " × " : ""}${i.label}`).join(", ")}</div><div className="text-sm text-ink-500">{p.user_name}, {p.mode === "pickup" ? `${dateShort(p.date)} ${p.slot}` : `drop-off code ${p.drop_code}`}, {p.recycler_name}, {kg(p.total_kg)}</div></div><Badge tone={STATUS_TONE[p.status]}>{p.status_label}</Badge></div>
            {p.address && <p className="mt-1 text-sm text-ink-700">{p.address.line}, {p.address.city}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              {p.next_statuses.filter((n: any) => n.status !== "cancelled").map((n: any) => n.status === "verified"
                ? <Button key={n.status} size="sm" variant="signal" onClick={() => setVerifying(verifying === p.id ? null : p.id)}>Verify and award points</Button>
                : <Button key={n.status} size="sm" variant="outline" loading={busy === p.id} onClick={() => move(p.id, { status: n.status })}>{n.status === "collector_assigned" ? "Assign collector" : n.label === "Picked up" ? "Mark picked up" : n.label === "Recycled" ? "Mark recycled" : `Mark ${n.label.toLowerCase()}`}</Button>)}
            </div>
            {verifying === p.id && (
              <div className="mt-3 grid gap-3 rounded-xl bg-mist-50 p-4 sm:grid-cols-[1fr_auto]">
                <div className="space-y-3"><Field label="Weighed weight in kg (optional)" hint="Leave blank to use the estimate."><input className={inputCls} type="number" step="0.01" min="0" value={weight} onChange={(e) => setWeight(e.target.value)} /></Field>
                  <label className="flex min-h-11 items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[#0E5257]" checked={match} onChange={(e) => setMatch(e.target.checked)} />Items match what the resident declared</label></div>
                <div className="flex items-end"><Button loading={busy === p.id} onClick={() => move(p.id, { status: "verified", verified_weight_kg: weight ? Number(weight) : undefined, verified_match: match })}>Confirm verification</Button></div>
              </div>
            )}
            {p.rewards && <p className="mt-2 text-sm text-ok">Awarded {p.rewards.points} points, {kg(p.rewards.kg)} diverted.</p>}
          </Card></li>))}</ul>
      )}
    </div>
  );
}

function FraudTab() {
  const { data, error, reload } = useAsync(() => api.get("/admin/fraud"), []);
  const [busy, setBusy] = useState<string | null>(null);
  const resolve = async (id: string, action: string) => { setBusy(id); try { await api.post(`/admin/fraud/${id}/resolve`, { action }); reload(); } finally { setBusy(null); } };
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return <PageSkeleton />;
  return data.length === 0 ? <Empty title="Nothing to review" body="Flagged submissions show up here with the reason." /> : (
    <ul className="space-y-3">{data.map((f: any) => (
      <li key={f.id}><Card>
        <div className="flex flex-wrap items-start justify-between gap-2"><div><div className="font-semibold">Suspicious submission detected</div><div className="text-sm text-ink-500">{f.user_name}, {f.item ?? "item"}, {timeAgo(f.created_at)}</div></div><Badge tone={f.status === "open" ? "alert" : f.status === "approved" ? "ok" : "neutral"}>{f.status}</Badge></div>
        <p className="mt-2 text-sm"><strong>Reason:</strong> {f.details?.join(" ") || f.reasons.join(", ")}</p>
        <div className="mt-1 flex flex-wrap gap-1.5">{f.reasons.map((r: string) => <Badge key={r} tone="signal">{r.toLowerCase().replace("_", " ")}</Badge>)}<Badge>score {f.score}</Badge>{f.held_points > 0 && <Badge tone="copper">{f.held_points} points held</Badge>}</div>
        <p className="mt-1 text-sm text-ink-500">Status: {f.status === "open" ? "pending verification" : f.status}</p>
        {f.status === "open" && <div className="mt-3 flex gap-2"><Button size="sm" loading={busy === f.id} onClick={() => resolve(f.id, "approve")}>Approve{f.held_points ? ` and release ${f.held_points} points` : ""}</Button><Button size="sm" variant="outline" onClick={() => resolve(f.id, "reject")}>Reject</Button></div>}
      </Card></li>))}</ul>
  );
}

function AiTab() {
  const { data, error, reload } = useAsync(() => api.get("/admin/predictions"), []);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return <PageSkeleton />;
  return (
    <Card className="overflow-x-auto p-0"><table className="w-full min-w-[640px] text-left text-sm"><caption className="sr-only">Recent AI classifications</caption>
      <thead className="border-b border-mist-200 bg-mist-50 text-ink-500"><tr>{["When", "Resident", "AI said", "Final", "Confidence", "Provider", "Corrected"].map((h) => <th key={h} scope="col" className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
      <tbody>{data.map((p: any) => <tr key={p.id} className="border-b border-mist-200 last:border-0"><td className="px-4 py-2 text-ink-500">{timeAgo(p.at)}</td><td className="px-4 py-2">{p.user_name}</td><td className="px-4 py-2">{p.predicted}</td><td className="px-4 py-2">{p.final}</td><td className="px-4 py-2 tabular-nums">{p.confidence != null ? `${Math.round(p.confidence * 100)}%` : "–"}</td><td className="px-4 py-2">{p.provider}</td><td className="px-4 py-2">{p.corrected ? <Badge tone="signal">yes</Badge> : <Badge tone="ok">no</Badge>}</td></tr>)}</tbody></table></Card>
  );
}

function AnalyticsTab() {
  const { data, error, reload } = useAsync(() => api.get("/admin/dashboard"), []);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return <PageSkeleton />;
  const a = data.analytics, q = data.queues;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {([["Submissions", num(a.total_submissions), `${num(a.verified_submissions)} verified`], ["Diverted", kg(a.kg_diverted), "verified weight"], ["CO₂e avoided", `${num(a.co2e_kg_avoided)} kg`, "estimate"], ["Recycling value", inr(a.recycling_value_inr), "estimate"],
          ["Participation", pct(a.participation_rate), `${a.repeat_users} repeat users`], ["Pickup completion", pct(a.pickup_completion_rate), `${q.pickups_open} open`], ["Challenge completion", pct(a.challenge_completion_rate), ""], ["Open fraud flags", String(a.open_fraud_flags), `${q.to_verify} awaiting verification`]] as const).map(([l, v, s]) => <Card key={l}><Stat label={l} value={v} sub={s} /></Card>)}
      </div>
      <Card><h2 className="text-xl font-semibold">AI accuracy feedback</h2><p className="text-sm text-ink-500">Human-in-the-loop: every confirmation records whether the person had to correct the AI. {a.ai_accuracy.n} confirmed predictions.</p>
        <div className="mt-3 flex items-end justify-between"><div><div className="font-display text-4xl font-semibold tabular-nums">{a.ai_accuracy.correct_first_attempt_pct}%</div><div className="text-sm text-ink-500">correct on first attempt</div></div><div className="text-right"><div className="font-display text-4xl font-semibold tabular-nums text-copper">{a.ai_accuracy.corrected_pct}%</div><div className="text-sm text-ink-500">user corrected</div></div></div>
        <div className="mt-3"><ProgressBar pct={a.ai_accuracy.correct_first_attempt_pct} label="Correct on first attempt" /></div></Card>
      <Card><h2 className="text-xl font-semibold">Recent admin and collector actions</h2>
        <ul className="mt-2 divide-y divide-mist-200 text-sm">{data.audit_recent.length === 0 ? <li className="py-2 text-ink-500">No actions recorded yet.</li> : data.audit_recent.map((r: any) => <li key={r.id} className="flex justify-between gap-3 py-2"><span>{r.actor_name} <span className="text-ink-500">({r.actor_role?.toLowerCase()})</span>: <code>{r.action}</code></span><span className="text-ink-400">{timeAgo(r.at)}</span></li>)}</ul></Card>
      <p className="text-xs text-ink-500">{a.data_note}</p>
    </div>
  );
}

function PeopleTab() {
  const { data, error, reload } = useAsync(() => api.get("/admin/users"), []);
  const [f, setF] = useState({ user_id: "", points: 25, reason: "" });
  const [msg, setMsg] = useState<{ tone: "ok" | "alert"; text: string } | null>(null);
  const adjust = async () => { setMsg(null); try { await api.post("/admin/points/adjust", f); setMsg({ tone: "ok", text: "Adjustment recorded in the ledger and audit log." }); reload(); } catch (e) { setMsg({ tone: "alert", text: (e as Error).message }); } };
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return <PageSkeleton />;
  return (
    <div className="space-y-4">
      <Card><h2 className="text-xl font-semibold">Export CSV</h2><div className="mt-3 flex flex-wrap gap-2">{["users", "submissions", "pickups", "ledger", "impact"].map((k) => <Button key={k} variant="outline" size="sm" onClick={() => api.download(`/admin/export/${k}`, `reloop_${k}.csv`)}>Download {k}</Button>)}</div></Card>
      <Card><h2 className="text-xl font-semibold">Adjust points</h2><p className="text-sm text-ink-500">Every adjustment is a ledger row with your name on it.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-4"><Field label="Person"><select className={inputCls} value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })}><option value="">Choose…</option>{data.filter((u: any) => u.role === "USER").map((u: any) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></Field><Field label="Points"><input className={inputCls} type="number" value={f.points} onChange={(e) => setF({ ...f, points: Number(e.target.value) })} /></Field><div className="sm:col-span-2"><Field label="Reason"><input className={inputCls} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} maxLength={120} /></Field></div></div>
        <Button className="mt-3" disabled={!f.user_id || f.reason.length < 3} onClick={adjust}>Record adjustment</Button>{msg && <div className="mt-3"><Notice tone={msg.tone}>{msg.text}</Notice></div>}</Card>
      <Card className="overflow-x-auto p-0"><table className="w-full min-w-[560px] text-left text-sm"><caption className="sr-only">Users</caption><thead className="border-b border-mist-200 bg-mist-50 text-ink-500"><tr>{["Name", "Role", "Building", "Points", "Items"].map((h) => <th key={h} scope="col" className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
        <tbody>{data.map((u: any) => <tr key={u.id} className="border-b border-mist-200 last:border-0"><td className="px-4 py-2"><div className="font-medium">{u.name}</div><div className="text-xs text-ink-500">{u.email}</div></td><td className="px-4 py-2">{u.role.toLowerCase().replace("_", " ")}</td><td className="px-4 py-2">{u.building}</td><td className="px-4 py-2 tabular-nums">{num(u.points)}</td><td className="px-4 py-2 tabular-nums">{num(u.items)}</td></tr>)}</tbody></table></Card>
    </div>
  );
}

function RecyclersTab() {
  const { data, error, reload } = useAsync(() => api.get("/admin/recyclers"), []);
  const opts = useAsync(() => api.get("/waste/options"), []);
  const [f, setF] = useState({ name: "", address: "", lat: "", lng: "", accepts: [] as string[], pickup_available: false });
  const [msg, setMsg] = useState<{ tone: "ok" | "alert"; text: string } | null>(null);
  const cats = Array.from(new Map<string, string>((opts.data?.items ?? []).map((i: any) => [i.category, i.category_label])).entries());
  const setVerify = async (id: string, verification_status: string) => { await api.patch(`/admin/recyclers/${id}`, { verification_status }); reload(); };
  const add = async () => {
    setMsg(null);
    try { await api.post("/admin/recyclers", { name: f.name, address: f.address, lat: Number(f.lat), lng: Number(f.lng), accepts: f.accepts, pickup_available: f.pickup_available }); setMsg({ tone: "ok", text: "Recycler added as not verified." }); reload(); }
    catch (e) { setMsg({ tone: "alert", text: e instanceof ApiError ? e.message : "Couldn't add." }); }
  };
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return <PageSkeleton />;
  return (
    <div className="space-y-4">
      <Notice tone="signal">Only mark a recycler "verified" after checking its authorisation with the state pollution control board. Entries below marked demo are fictional.</Notice>
      <ul className="space-y-2">{data.map((r: any) => <li key={r.id}><Card className="flex flex-wrap items-center justify-between gap-3"><div><div className="font-semibold">{r.name}</div><div className="text-sm text-ink-500">{r.address}</div><div className="mt-1 flex gap-1.5"><Badge tone={r.verification.status === "unverified" ? "neutral" : "petrol"}>{r.verification.label}</Badge>{r.demo && <Badge tone="signal">Demo data</Badge>}</div></div>
        <div className="flex gap-2">{r.verification.status === "verified" ? <Button size="sm" variant="outline" onClick={() => setVerify(r.id, "unverified")}>Mark not verified</Button> : <Button size="sm" variant="outline" onClick={() => setVerify(r.id, "verified")}>Mark verified</Button>}</div></Card></li>)}</ul>
      <Card><h2 className="text-xl font-semibold">Add a recycler</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2"><Field label="Name"><input className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field><Field label="Address"><input className={inputCls} value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field><Field label="Latitude"><input className={inputCls} inputMode="decimal" value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} /></Field><Field label="Longitude"><input className={inputCls} inputMode="decimal" value={f.lng} onChange={(e) => setF({ ...f, lng: e.target.value })} /></Field></div>
        <fieldset className="mt-3"><legend className="text-sm font-medium text-ink-700">Accepts</legend><div className="mt-1 flex flex-wrap gap-2">{cats.map(([k, l]) => <label key={k} className="flex min-h-9 items-center gap-2 rounded-lg border border-mist-300 px-3 text-sm"><input type="checkbox" className="accent-[#0E5257]" checked={f.accepts.includes(k)} onChange={(e) => setF({ ...f, accepts: e.target.checked ? [...f.accepts, k] : f.accepts.filter((x) => x !== k) })} />{l}</label>)}</div></fieldset>
        <label className="mt-3 flex min-h-11 items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[#0E5257]" checked={f.pickup_available} onChange={(e) => setF({ ...f, pickup_available: e.target.checked })} />Offers pickup</label>
        <Button onClick={add} disabled={!f.name || !f.address || !f.lat || !f.lng || f.accepts.length === 0}>Add recycler</Button>{msg && <div className="mt-3"><Notice tone={msg.tone}>{msg.text}</Notice></div>}</Card>
    </div>
  );
}

export default function Ops() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN";
  const [tab, setTab] = useState("pickups");
  const tabs = [{ id: "pickups", label: "Pickups" }, ...(admin ? [{ id: "fraud", label: "Fraud review" }, { id: "ai", label: "AI review" }, { id: "analytics", label: "Analytics" }, { id: "people", label: "People and exports" }, { id: "recyclers", label: "Recyclers" }] : [])];
  return (
    <div>
      <PageHeader title="Operations" subtitle={admin ? "Verify pickups, review flags, inspect AI results and manage data." : "Your pickup queue. Collect, weigh and verify."} actions={tabs.length > 1 ? <Tabs label="Operations sections" value={tab} onChange={setTab} tabs={tabs} /> : undefined} />
      {tab === "pickups" && <PickupsTab />}{tab === "fraud" && <FraudTab />}{tab === "ai" && <AiTab />}{tab === "analytics" && <AnalyticsTab />}{tab === "people" && <PeopleTab />}{tab === "recyclers" && <RecyclersTab />}
    </div>
  );
}
