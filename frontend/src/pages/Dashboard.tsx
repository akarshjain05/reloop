import { useState } from "react";
import { ArrowRight, Flame, Trophy } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, ErrorBox, LinkButton, PageHeader, PageSkeleton, ProgressBar, Ring, Stat, Empty } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn, inr, kg, num, timeAgo } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-white/15 px-3 py-1 text-sm font-medium tabular-nums">{children}</span>;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data: d, error, loading, reload } = useAsync(() => api.get("/dashboard"), []);
  const [joining, setJoining] = useState(false);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !d) return <PageSkeleton />;
  const nba = d.next_best_action, est = nba.estimate, ch = d.challenge, b = d.building;
  const join = async () => { setJoining(true); try { await api.post(`/challenges/${ch.id}/join`); reload(); } finally { setJoining(false); } };
  return (
    <div className="space-y-6">
      <PageHeader title={`Welcome back, ${user?.name.split(" ")[0] ?? ""}`} subtitle={b ? `${b.name}. Here's what your recycling did lately and the best next step.` : "Here's your recycling at a glance."} />

      <Card tone="petrol" className="rounded-hero p-6 sm:p-8" aria-labelledby="nba-title">
        <div className="text-sm font-medium text-petrol-100">Your next best action</div>
        <h2 id="nba-title" className="mt-1 max-w-3xl text-3xl font-semibold sm:text-4xl">{nba.title}</h2>
        <p className="mt-2 max-w-2xl text-lg text-petrol-100">{nba.body}</p>
        {est && (
          <div className="mt-4">
            <div className="flex flex-wrap gap-2">
              {est.points != null && <Chip>+{est.points} points</Chip>}
              {est.items != null && <Chip>+{est.items} items</Chip>}
              {est.kg != null && <Chip>{num(est.kg, 1)} kg diverted</Chip>}
              {est.co2e_kg != null && <Chip>~{num(est.co2e_kg, 1)} kg CO₂e avoided</Chip>}
            </div>
            <p className="mt-2 text-sm text-petrol-200">{nba.estimate_label ?? "Estimates based on configured assumptions"}</p>
          </div>
        )}
        <LinkButton to={nba.cta.route} variant="signal" size="lg" className="mt-6">{nba.cta.label}<ArrowRight className="h-5 w-5" aria-hidden="true" /></LinkButton>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card aria-label="ReLoop points" className="flex items-center gap-5">
          <Ring pct={d.points.tier.progress_pct} size={104}><div><div className="font-display text-2xl font-semibold tabular-nums">{num(d.points.total)}</div><div className="text-xs text-ink-500">points</div></div></Ring>
          <div><Badge tone="petrol">{d.points.tier.name}</Badge>
            <p className="mt-2 text-[15px]">{d.points.tier.next_name ? `${d.points.tier.points_to_next} more points to reach ${d.points.tier.next_name}.` : "You've reached the top tier."}</p>
            {d.points.pending_review > 0 && <p className="mt-1 text-sm text-ink-500">{d.points.pending_review} more pending review.</p>}</div>
        </Card>
        <Card aria-label="Rank" className="flex items-center gap-4">
          <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-signal-100 text-[#6E4A00]"><Trophy className="h-7 w-7" aria-hidden="true" /></div>
          <div><div className="font-display text-3xl font-semibold tabular-nums">{d.rank.position ? `#${d.rank.position}` : "Ready"}<span className="text-lg font-normal text-ink-500">{d.rank.position ? ` of ${d.rank.of}` : ""}</span></div><p className="text-sm text-ink-700">{d.rank.message}</p></div>
        </Card>
        <Card aria-label="Streak">
          <div className="flex items-center gap-2"><Flame className="h-5 w-5 text-copper" aria-hidden="true" /><span className="font-display text-2xl font-semibold tabular-nums">{d.streak.weeks}</span><span className="text-ink-500">week streak</span></div>
          <div className="mt-3 flex gap-1" role="img" aria-label={`Activity over the last 12 weeks, ${d.streak.weekly.filter((w: any) => w.active).length} active`}>
            {d.streak.weekly.map((w: any) => <span key={w.week} title={w.week} className={cn("h-6 flex-1 rounded", w.active ? "bg-petrol-500" : "bg-mist-200")} />)}
          </div>
          <p className="mt-2 text-sm text-ink-500">One verified item a week keeps it going.</p>
        </Card>
      </div>

      <Card aria-label="Last 30 days">
        <h2 className="mb-4 text-xl font-semibold">Last 30 days</h2>
        <div className="grid grid-cols-2 gap-5 lg:grid-cols-4">
          <Stat label="Diverted" value={kg(d.month.kg)} sub="from landfill, verified" />
          <Stat label="Items processed" value={num(d.month.items)} />
          <Stat label="Recycling value" value={inr(d.month.value_inr)} sub="estimate, curated demo prices" />
          <Stat label="CO₂e avoided" value={`${num(d.month.co2e_kg, 1)} kg`} sub="illustrative estimate" />
        </div>
        <p className="mt-4 rounded-xl bg-mist-50 p-3 text-[15px]">{d.impact_story}</p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {b && (
          <Card aria-label="Building ReLoop Score">
            <div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">{b.name}</h2><p className="text-sm text-ink-500">ReLoop Score, last 30 days</p></div>
              <div className="text-right"><span className="font-display text-5xl font-semibold tabular-nums">{b.score}</span><span className="text-ink-500"> / 100</span></div></div>
            <ul className="mt-4 space-y-2">
              {b.components.map((c: any) => <li key={c.key}><div className="flex justify-between text-sm"><span>{c.label}</span><span className="tabular-nums text-ink-500">{c.points} of {c.weight}</span></div><ProgressBar pct={c.value * 100} label={c.label} tone={c.value < 0.6 ? "signal" : "petrol"} /></li>)}
            </ul>
            <Link to="/org" className="mt-4 inline-flex h-10 items-center gap-1 text-sm font-semibold text-petrol-700 underline-offset-4 hover:underline">See how it's calculated and what would improve it<ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
          </Card>
        )}
        <div className="space-y-4">
          {ch && (
            <Card aria-label="Challenge">
              <div className="flex items-center justify-between gap-2"><h2 className="text-xl font-semibold">{ch.title}</h2><Badge tone="copper">{ch.days_left} days left</Badge></div>
              <p className="mt-1 text-sm text-ink-500">{ch.description}</p>
              <div className="mt-3 flex justify-between text-sm"><span className="tabular-nums">{num(ch.progress, ch.unit === "kg" ? 0 : 0)} of {num(ch.goal)} {ch.unit}</span><span className="tabular-nums font-semibold">{ch.pct}%</span></div>
              <ProgressBar pct={ch.pct} tone="copper" label={ch.title} />
              <div className="mt-3 flex items-center justify-between">{ch.joined ? <span className="text-sm text-ink-700">You've contributed {num(ch.my_contribution, 1)} {ch.unit}. Verified items add 10% bonus points.</span> : <Button size="sm" loading={joining} onClick={join}>Join challenge</Button>}<Link to="/challenges" className="text-sm font-semibold text-petrol-700">All challenges</Link></div>
            </Card>
          )}
          <Card aria-label="Recent activity">
            <h2 className="mb-2 text-xl font-semibold">Recent activity</h2>
            {d.recent.length === 0 ? <Empty title="Nothing yet" body="Scan your first item to start your history." action={<LinkButton to="/scan" size="sm">Scan an item</LinkButton>} /> : (
              <ul className="divide-y divide-mist-200">{d.recent.slice(0, 5).map((r: any, i: number) => <li key={i} className="flex items-baseline justify-between gap-3 py-2.5"><div className="min-w-0"><div className="truncate font-medium">{r.title}</div><div className="text-sm text-ink-500">{r.detail}</div></div><span className="shrink-0 text-xs text-ink-400">{timeAgo(r.at)}</span></li>)}</ul>
            )}
          </Card>
        </div>
      </div>
      <p className="text-xs text-ink-500">{d.disclaimer}</p>
    </div>
  );
}
