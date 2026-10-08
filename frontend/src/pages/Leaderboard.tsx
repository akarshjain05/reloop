import { useState } from "react";
import { Trophy } from "lucide-react";
import { Badge, Card, Empty, ErrorBox, PageHeader, PageSkeleton, ProgressBar, Tabs } from "../components/ui";
import { api } from "../lib/api";
import { cn, kg, num } from "../lib/format";
import { useAsync } from "../lib/useAsync";

type Scope = "global" | "campus" | "building" | "neighborhood";
const PATH: Record<Scope, string> = { global: "/leaderboard", campus: "/leaderboard/campus", building: "/leaderboard/building", neighborhood: "/leaderboard/neighborhood" };
const RANK_TONE = ["bg-signal text-ink", "bg-mist-300 text-ink", "bg-copper-100 text-copper"];

export default function Leaderboard() {
  const [scope, setScope] = useState<Scope>("global");
  const [period, setPeriod] = useState<"month" | "all">("month");
  const { data: d, error, loading, reload } = useAsync(() => api.get(`${PATH[scope]}?period=${period}`), [scope, period]);
  return (
    <div>
      <PageHeader title="Leaderboard" subtitle="Friendly competition, scored on verified recycling only." actions={<Tabs label="Time period" value={period} onChange={setPeriod} tabs={[{ id: "month", label: "Last 30 days" }, { id: "all", label: "All time" }]} />} />
      <Tabs label="Leaderboard scope" value={scope} onChange={setScope} tabs={[{ id: "global", label: "Global" }, { id: "campus", label: "Campus" }, { id: "building", label: "Building" }, { id: "neighborhood", label: "Neighborhood" }]} />
      <div className="mt-5 space-y-4">
        {error ? <ErrorBox error={error} onRetry={reload} /> : loading && !d ? <PageSkeleton /> : d && (
          <>
            <Card tone="petrol" className="rounded-hero">
              <div className="flex flex-wrap items-center gap-4"><div className="grid h-14 w-14 place-items-center rounded-2xl bg-white/15"><Trophy className="h-7 w-7 text-signal" aria-hidden="true" /></div>
                <div className="min-w-0 flex-1"><div className="font-display text-2xl font-semibold">{d.me.rank ? `You are #${d.me.rank}` : "Your spot is waiting"}</div><p className="text-petrol-100">{d.me.message}</p></div></div>
              {d.me.tier?.next_name && <div className="mt-4"><div className="mb-1 flex justify-between text-sm text-petrol-100"><span>{d.me.tier.name}</span><span>{d.me.tier.next_name}</span></div><div className="[&_[role=progressbar]]:bg-white/20"><ProgressBar pct={d.me.tier.progress_pct} tone="signal" label={`Progress to ${d.me.tier.next_name}`} /></div></div>}
            </Card>
            <Card className="overflow-hidden p-0">
              <h2 className="px-5 pt-5 text-xl font-semibold">{d.title}</h2>
              {d.entries.length === 0 ? <div className="p-5"><Empty title="No entries yet" body="Be the first to verify a recycling action here." /></div> : (
                <div className="overflow-x-auto"><table className="mt-3 w-full min-w-[480px] text-left">
                  <caption className="sr-only">{d.title}</caption>
                  <thead className="border-y border-mist-200 bg-mist-50 text-sm text-ink-500"><tr><th scope="col" className="w-16 px-5 py-2 font-medium">Rank</th><th scope="col" className="py-2 font-medium">{d.unit === "building" ? "Building" : "Name"}</th><th scope="col" className="py-2 text-right font-medium">Points</th><th scope="col" className="py-2 text-right font-medium">Diverted</th><th scope="col" className="hidden py-2 text-right font-medium sm:table-cell">Items</th><th scope="col" className="hidden px-5 py-2 text-right font-medium sm:table-cell">Streak</th></tr></thead>
                  <tbody>{d.entries.map((e: any) => (
                    <tr key={e.id} className={cn("border-b border-mist-200 last:border-0", e.is_me && "bg-signal-100/60")}>
                      <td className="px-5 py-3"><span className={cn("grid h-8 w-8 place-items-center rounded-full text-sm font-bold tabular-nums", RANK_TONE[e.rank - 1] ?? "bg-mist-100 text-ink-700")}>{e.rank}</span></td>
                      <td className="py-3"><div className="flex flex-wrap items-center gap-2 font-medium">{e.name}{e.is_me && <Badge tone="petrol">You</Badge>}</div>{e.org && <div className="text-xs text-ink-500">{e.org}{e.participants != null ? `, ${e.participants} taking part` : ""}</div>}</td>
                      <td className="py-3 text-right font-display text-lg font-semibold tabular-nums">{num(e.points)}</td>
                      <td className="py-3 text-right tabular-nums">{kg(e.kg)}</td>
                      <td className="hidden py-3 text-right tabular-nums sm:table-cell">{num(e.items)}</td>
                      <td className="hidden px-5 py-3 text-right tabular-nums sm:table-cell">{e.streak == null ? "–" : `${e.streak} wk`}</td>
                    </tr>))}</tbody>
                </table></div>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
