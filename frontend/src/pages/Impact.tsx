import { ReactNode } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, ErrorBox, LinkButton, PageHeader, PageSkeleton, ProgressBar, Empty } from "../components/ui";
import { api } from "../lib/api";
import { cn, kg, monthLabel, num } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const axis = { fontSize: 12, fill: "#566A6F" };
function ChartCard({ title, caption, children }: { title: string; caption: string; children: ReactNode }) {
  return (
    <Card>
      <figure><figcaption className="mb-3"><h2 className="text-xl font-semibold">{title}</h2><p className="text-sm text-ink-500">{caption}</p></figcaption><div className="h-56" role="img" aria-label={`${title}. ${caption}`}>{children}</div></figure>
    </Card>
  );
}

export default function Impact() {
  const { data: d, error, loading, reload } = useAsync(() => api.get("/impact"), []);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !d) return <PageSkeleton />;
  const series = d.monthly.map((m: any) => ({ ...m, label: monthLabel(m.month) }));
  const empty = d.totals.all.items === 0;
  const mats = Object.entries(d.materials_kg as Record<string, number>).sort((a, b) => b[1] - a[1]);
  const maxMat = mats[0]?.[1] || 1;
  const tip = { contentStyle: { borderRadius: 12, border: "1px solid #E1E8EA", fontSize: 13 } };
  return (
    <div className="space-y-6">
      <PageHeader title="My impact" subtitle="What your verified recycling actions added up to, and what the numbers mean." />
      {empty ? <Empty title="Your impact starts with the first verified item" body="Scan something, schedule it, and this page fills in." action={<LinkButton to="/scan" variant="signal">Scan an item</LinkButton>} /> : (
        <>
          <Card tone="petrol" className="rounded-hero">
            <h2 className="text-2xl font-semibold">Your actions this month</h2>
            <p className="mt-2 max-w-3xl text-lg text-petrol-100">You processed <strong className="text-white">{d.this_month.items} items</strong> and diverted <strong className="text-white">{kg(d.this_month.kg)}</strong> from landfill. Your verified recycling actions prevented an estimated <strong className="text-white">{num(d.this_month.co2e_kg, 1)} kg CO₂e</strong> associated with disposal.</p>
            <p className="mt-2 text-sm text-petrol-200">All-time: {kg(d.totals.all.kg)}, {num(d.totals.all.items)} items, {num(d.totals.all.points)} points. CO₂e is an illustrative estimate from configured impact factors.</p>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Waste diverted" caption={`Kilograms per month. Latest: ${kg(series[series.length - 1].kg)}.`}>
              <ResponsiveContainer width="100%" height="100%"><BarChart data={series}><CartesianGrid vertical={false} stroke="#E1E8EA" /><XAxis dataKey="label" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} width={36} /><Tooltip {...tip} formatter={(v: number) => [`${v} kg`, "Diverted"]} /><Bar dataKey="kg" fill="#0E5257" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Points earned" caption={`Points added to your ledger each month. Latest: ${num(series[series.length - 1].points)}.`}>
              <ResponsiveContainer width="100%" height="100%"><AreaChart data={series}><CartesianGrid vertical={false} stroke="#E1E8EA" /><XAxis dataKey="label" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} width={40} /><Tooltip {...tip} formatter={(v: number) => [num(v), "Points"]} /><Area type="monotone" dataKey="points" stroke="#D99A12" fill="#FDF1D4" strokeWidth={2.5} /></AreaChart></ResponsiveContainer>
            </ChartCard>
            <ChartCard title="CO₂e avoided (estimate)" caption="Illustrative estimate, from configured impact factors.">
              <ResponsiveContainer width="100%" height="100%"><LineChart data={series}><CartesianGrid vertical={false} stroke="#E1E8EA" /><XAxis dataKey="label" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} width={36} /><Tooltip {...tip} formatter={(v: number) => [`${v} kg`, "CO₂e (est.)"]} /><Line type="monotone" dataKey="co2e" stroke="#B9692E" strokeWidth={2.5} dot={{ r: 3 }} /></LineChart></ResponsiveContainer>
            </ChartCard>
            <ChartCard title="What you recycled" caption="Items by category over all time.">
              <ResponsiveContainer width="100%" height="100%"><BarChart data={d.categories} layout="vertical" margin={{ left: 20 }}><CartesianGrid horizontal={false} stroke="#E1E8EA" /><XAxis type="number" tick={axis} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="label" tick={axis} axisLine={false} tickLine={false} width={120} /><Tooltip {...tip} formatter={(v: number) => [v, "Items"]} /><Bar dataKey="items" fill="#14797F" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer>
            </ChartCard>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card><h2 className="text-xl font-semibold">Materials recovered (estimate)</h2><p className="text-sm text-ink-500">Recoverable material by weight, from each item's recovery score and typical composition.</p>
              <ul className="mt-4 space-y-3">{mats.map(([m, v]) => <li key={m}><div className="flex justify-between text-sm capitalize"><span>{m}</span><span className="tabular-nums">{kg(v, 2)}</span></div><ProgressBar pct={(v / maxMat) * 100} tone="copper" label={m} /></li>)}</ul></Card>
            <Card><h2 className="text-xl font-semibold">Participation streak</h2><p className="text-sm text-ink-500">{d.streak.weeks} week{d.streak.weeks === 1 ? "" : "s"} in a row with a verified action.</p>
              <div className="mt-4 grid grid-cols-12 gap-1" role="img" aria-label="Weekly activity for the last 12 weeks">{d.streak.weekly.map((w: any) => <span key={w.week} title={w.week} className={cn("h-10 rounded", w.active ? "bg-petrol-500" : "bg-mist-200")} />)}</div>
              <p className="mt-2 text-xs text-ink-500">Oldest to newest. Dark squares are weeks with at least one verified item.</p></Card>
          </div>
          <Card tone="mist"><h2 className="text-xl font-semibold">What the numbers mean</h2>
            <dl className="mt-3 grid gap-4 md:grid-cols-3">{d.explain.map((e: any) => <div key={e.label}><dt className="font-semibold">{e.label}</dt><dd className="text-sm text-ink-700">{e.meaning}</dd></div>)}</dl>
            <p className="mt-4 text-xs text-ink-500">{d.disclaimer}</p></Card>
        </>
      )}
    </div>
  );
}
