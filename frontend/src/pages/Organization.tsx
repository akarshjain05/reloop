import { FormEvent, useState } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Button, Card, Disclosure, ErrorBox, Field, inputCls, Notice, PageHeader, PageSkeleton, ProgressBar, Stat, Tabs } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn, kg, monthLabel, num, pct } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const axis = { fontSize: 12, fill: "#566A6F" };

export default function Organization() {
  const { user } = useAuth();
  const staff = user?.role === "ORGANIZATION_ADMIN" || user?.role === "ADMIN";
  const [scope, setScope] = useState<"org" | "building">(staff ? "org" : "building");
  const q = scope === "building" && staff ? `?scope=building&scope_id=${user?.building_id}` : staff ? "?scope=org" : "";
  const { data: d, error, loading, reload } = useAsync(() => api.get(`/org/summary${q}`), [q]);
  const [form, setForm] = useState({ title: "", goal: 50, days: 14 });
  const [msg, setMsg] = useState<{ tone: "ok" | "alert"; text: string } | null>(null);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !d) return <PageSkeleton />;
  const s = d.score, k = s.kpis, gap = d.gap;
  const trend = d.trend.map((t: any) => ({ ...t, label: monthLabel(t.month) }));
  const mix = gap.categories.map((c: any) => ({ label: c.label, Expected: Math.round(c.expected_share * 100), Collected: Math.round(c.actual_share * 100) }));
  const create = async (e: FormEvent) => {
    e.preventDefault(); setMsg(null);
    try {
      await api.post("/admin/challenges", { title: form.title || `${gap.drive?.label ?? "Collection"} drive`, description: `Collect ${form.goal} items in ${form.days} days.`, metric: "items", goal: Number(form.goal), reward_points: 500, days: Number(form.days), category: gap.top_gap?.category, scope: "org" });
      setMsg({ tone: "ok", text: "Campaign created. It now shows up under Challenges for your members." }); reload();
    } catch (err) { setMsg({ tone: "alert", text: err instanceof ApiError ? err.message : "Couldn't create the campaign." }); }
  };
  return (
    <div className="space-y-6">
      <PageHeader title={d.name} subtitle="ReLoop Score, participation and what would improve them. Every number links to an action." actions={staff ? <Tabs label="View" value={scope} onChange={setScope} tabs={[{ id: "org", label: "Whole campus" }, { id: "building", label: "My building" }]} /> : undefined} />

      <Card className="rounded-hero p-6 sm:p-8">
        <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
          <div><div className="text-sm text-ink-500">ReLoop Score, last {s.window_days} days</div><div className="font-display text-7xl font-bold leading-none tabular-nums text-petrol-600">{s.score}</div><div className="mt-1 text-ink-500">out of 100</div></div>
          <div>
            <h2 className="text-xl font-semibold">How it was calculated</h2>
            <ul className="mt-3 space-y-3">{s.components.map((c: any) => (
              <li key={c.key}><div className="flex flex-wrap items-baseline justify-between gap-2"><span className="font-medium">{c.label} <span className="text-sm font-normal text-ink-500">(weight {c.weight})</span></span><span className="font-display font-semibold tabular-nums">{c.points} <span className="text-sm font-normal text-ink-500">of {c.weight}</span></span></div><ProgressBar pct={c.value * 100} tone={c.value < 0.6 ? "signal" : "petrol"} label={c.label} /><p className="mt-0.5 text-sm text-ink-500">{c.detail}</p></li>))}</ul>
            <p className="mt-4 rounded-xl bg-mist-50 p-3 text-sm text-ink-700">{s.formula}</p>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Card><Stat label="Participation" value={pct(k.participation_rate)} sub={`${k.active_users} of ${k.members} members`} /></Card>
        <Card><Stat label="Verified disposal" value={pct(k.recycling_rate)} sub="of committed items" /></Card>
        <Card><Stat label="Diverted" value={kg(k.kg_30d)} sub={`target ${kg(k.target_kg, 0)}`} /></Card>
        <Card><Stat label="Items" value={num(k.items_30d)} sub="last 30 days" /></Card>
        <Card><Stat label="CO₂e avoided" value={`${num(k.co2e_kg_30d, 1)} kg`} sub="illustrative estimate" /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card><figure><figcaption><h2 className="text-xl font-semibold">Monthly trend</h2><p className="text-sm text-ink-500">Kilograms diverted and people taking part. All time: {kg(d.all_time.kg)}, {num(d.all_time.items)} items.</p></figcaption>
          <div className="mt-3 h-60" role="img" aria-label="Monthly kilograms diverted and participants"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={trend}><CartesianGrid vertical={false} stroke="#E1E8EA" /><XAxis dataKey="label" tick={axis} axisLine={false} tickLine={false} /><YAxis yAxisId="l" tick={axis} axisLine={false} tickLine={false} width={36} /><YAxis yAxisId="r" orientation="right" tick={axis} axisLine={false} tickLine={false} width={30} /><Tooltip contentStyle={{ borderRadius: 12, fontSize: 13 }} /><Legend wrapperStyle={{ fontSize: 12 }} /><Bar yAxisId="l" dataKey="kg" name="kg diverted" fill="#0E5257" radius={[6, 6, 0, 0]} /><Line yAxisId="r" dataKey="participants" name="people" stroke="#D99A12" strokeWidth={2.5} dot={{ r: 3 }} /></ComposedChart></ResponsiveContainer></div></figure></Card>
        <Card><figure><figcaption><h2 className="text-xl font-semibold">What's collected vs expected</h2><p className="text-sm text-ink-500">Share of items by category, last 90 days. {gap.basis}</p></figcaption>
          <div className="mt-3 h-60" role="img" aria-label="Collected share versus expected share by category"><ResponsiveContainer width="100%" height="100%"><BarChart data={mix} layout="vertical" margin={{ left: 24 }}><CartesianGrid horizontal={false} stroke="#E1E8EA" /><XAxis type="number" unit="%" tick={axis} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="label" tick={{ ...axis, fontSize: 11 }} axisLine={false} tickLine={false} width={120} /><Tooltip contentStyle={{ borderRadius: 12, fontSize: 13 }} /><Legend wrapperStyle={{ fontSize: 12 }} /><Bar dataKey="Expected" fill="#CBD6D9" radius={[0, 4, 4, 0]} /><Bar dataKey="Collected" fill="#14797F" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div></figure></Card>
      </div>

      {gap.top_gap && gap.drive && (
        <Card tone="petrol" className="rounded-hero p-6 sm:p-8">
          <div className="text-sm font-medium text-petrol-100">Next best action for {d.name}</div>
          <h2 className="mt-1 text-2xl font-semibold sm:text-3xl">{gap.top_gap.label} are falling behind. Run a collection drive.</h2>
          <p className="mt-2 max-w-2xl text-petrol-100">Only {pct(gap.top_gap.actual_share)} of collected items are {gap.top_gap.label.toLowerCase()}, against {pct(gap.top_gap.expected_share)} expected. A drive this weekend could add roughly:</p>
          <div className="mt-3 flex flex-wrap gap-2 text-sm font-medium">{[`+${gap.drive.est_items} items`, `${gap.drive.est_kg} kg diverted`, `~${gap.drive.est_co2e_kg} kg CO₂e avoided`].map((t) => <span key={t} className="rounded-full bg-white/15 px-3 py-1 tabular-nums">{t}</span>)}</div>
          <p className="mt-2 text-sm text-petrol-200">{gap.drive.basis}</p>
          {staff && (
            <div className="mt-5"><Disclosure summary="Create this campaign" defaultOpen={false}>
              <form onSubmit={create} className="mt-2 grid gap-3 text-ink sm:grid-cols-3">
                <Field label="Title"><input className={inputCls} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder={`${gap.drive.label} drive`} maxLength={80} /></Field>
                <Field label="Goal (items)"><input className={inputCls} type="number" min={1} value={form.goal} onChange={(e) => setForm({ ...form, goal: Number(e.target.value) })} /></Field>
                <Field label="Days"><input className={inputCls} type="number" min={1} max={120} value={form.days} onChange={(e) => setForm({ ...form, days: Number(e.target.value) })} /></Field>
                <div className="sm:col-span-3"><Button type="submit" variant="signal">Launch campaign</Button></div>
              </form>
              {msg && <div className="mt-3"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
            </Disclosure></div>
          )}
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card><h2 className="text-xl font-semibold">Top contributors</h2><p className="text-sm text-ink-500">Last 30 days, by points.</p>
          <ol className="mt-3 divide-y divide-mist-200">{d.top_contributors.map((c: any, i: number) => <li key={c.id} className="flex items-center justify-between gap-2 py-2"><span><span className="mr-2 text-ink-400 tabular-nums">{i + 1}</span>{c.name}</span><span className="font-semibold tabular-nums">{num(c.points)}</span></li>)}</ol></Card>
        <Card><h2 className="text-xl font-semibold">Top waste categories</h2><p className="text-sm text-ink-500">Items, last 90 days.</p>
          <ul className="mt-3 space-y-3">{d.top_categories.map((c: any) => <li key={c.category}><div className="flex justify-between text-sm"><span>{c.label}</span><span className="tabular-nums">{num(c.items)} items, {kg(c.kg)}</span></div><ProgressBar pct={(c.items / (d.top_categories[0]?.items || 1)) * 100} label={c.label} /></li>)}</ul></Card>
        {d.top_buildings.length > 0 ? (
          <Card><h2 className="text-xl font-semibold">Buildings</h2><p className="text-sm text-ink-500">ReLoop Score, last 30 days.</p>
            <ol className="mt-3 divide-y divide-mist-200">{d.top_buildings.map((b: any, i: number) => <li key={b.id} className="flex items-center justify-between gap-2 py-2"><span><span className="mr-2 text-ink-400 tabular-nums">{i + 1}</span>{b.name}</span><Badge tone={b.score >= 70 ? "ok" : b.score >= 55 ? "petrol" : "signal"}>{b.score}</Badge></li>)}</ol></Card>
        ) : (
          <Card><h2 className="text-xl font-semibold">Collection campaigns</h2>
            <ul className="mt-3 space-y-3">{d.campaigns.map((c: any) => <li key={c.id}><div className="flex justify-between text-sm"><span>{c.title}</span><span className="tabular-nums">{c.pct}%</span></div><ProgressBar pct={c.pct} tone="copper" label={c.title} /></li>)}</ul></Card>
        )}
      </div>
      {d.top_buildings.length > 0 && <Card><h2 className="text-xl font-semibold">Collection campaigns</h2><ul className="mt-3 grid gap-3 sm:grid-cols-2">{d.campaigns.map((c: any) => <li key={c.id}><div className="flex justify-between text-sm"><span>{c.title}{c.status === "completed" ? " (complete)" : ""}</span><span className="tabular-nums">{num(c.progress)} of {num(c.goal)} {c.metric === "kg" ? "kg" : "items"}</span></div><ProgressBar pct={c.pct} tone="copper" label={c.title} /></li>)}</ul></Card>}
    </div>
  );
}
