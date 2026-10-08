import { useState } from "react";
import { Flag } from "lucide-react";
import { Badge, Button, Card, Empty, ErrorBox, Notice, PageHeader, PageSkeleton, ProgressBar } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { num } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Challenges() {
  const { data, error, loading, reload } = useAsync(() => api.get("/challenges"), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const join = async (id: string) => {
    setBusy(id); setErr(null);
    try { await api.post(`/challenges/${id}/join`); reload(); } catch (e) { setErr(e instanceof ApiError ? e.message : "Couldn't join."); } finally { setBusy(null); }
  };
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading && !data) return <PageSkeleton />;
  return (
    <div>
      <PageHeader title="Challenges" subtitle="Shared goals for your campus or society. Progress moves when a verified pickup or drop-off is recorded." />
      {err && <div className="mb-3"><Notice tone="alert">{err}</Notice></div>}
      {data.length === 0 ? <Empty icon={<Flag className="h-6 w-6" />} title="No challenges right now" body="New community goals show up here." /> : (
        <ul className="grid gap-4 md:grid-cols-2">
          {data.map((c: any) => (
            <li key={c.id}>
              <Card className="flex h-full flex-col">
                <div className="flex items-start justify-between gap-2"><h2 className="text-2xl font-semibold leading-tight">{c.title}</h2>{c.status === "completed" ? <Badge tone="ok">Completed</Badge> : <Badge tone="copper">{c.days_left} days left</Badge>}</div>
                <p className="mt-1 text-ink-700">{c.description}</p>
                <div className="mt-4"><div className="mb-1 flex justify-between"><span className="tabular-nums"><strong className="font-display text-2xl">{num(c.progress)}</strong> <span className="text-ink-500">of {num(c.goal)} {c.unit}</span></span><span className="font-semibold tabular-nums">{c.pct}%</span></div><ProgressBar pct={c.pct} tone="copper" label={c.title} /></div>
                <p className="mt-3 text-sm text-ink-500">Reward: {num(c.reward_points)} community points shared among contributors. {c.participants} taking part. Joined challenges add a 10% bonus to matching verified items.</p>
                <div className="mt-auto pt-4">{c.joined ? <p className="rounded-xl bg-ok-100 p-3 text-sm text-ok">You're in. You've contributed {num(c.my_contribution, 1)} {c.unit} so far.</p> : c.is_active ? <Button loading={busy === c.id} onClick={() => join(c.id)}>Join challenge</Button> : null}</div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
