import { useMemo, useState } from "react";
import { Store } from "lucide-react";
import { Badge, Button, Card, Empty, ErrorBox, inputCls, LinkButton, Notice, PageHeader, PageSkeleton, Tabs } from "../components/ui";
import { api } from "../lib/api";
import { ACTION_LABEL, inrRange } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Exchange() {
  const { data, error, loading, reload } = useAsync(() => api.get("/prices/catalog"), []);
  const [cat, setCat] = useState("all");
  const [cond, setCond] = useState("all");
  const [act, setAct] = useState("all");
  const rows = useMemo(() => (data?.items ?? []).filter((r: any) => (cat === "all" || r.category === cat) && (cond === "all" || r.condition === cond) && (act === "all" || r.action.primary === act)), [data, cat, cond, act]);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !data) return <PageSkeleton />;
  const cats = Array.from(new Map<string, string>(data.items.map((r: any) => [r.category, r.category_label])).entries());
  const conds = Array.from(new Map<string, string>(data.items.map((r: any) => [r.condition, r.condition_label])).entries());
  return (
    <div>
      <PageHeader title="ReLoop Exchange" subtitle="See what common electronics are worth and whether to resell, repair, recycle or donate them." />
      <Notice tone="signal"><strong>{data.label}.</strong> {data.source} Last updated {data.updated}. These are not live market prices. {data.disclaimer}</Notice>

      <div className="my-5 flex flex-wrap items-end gap-3">
        <Tabs label="Recommended action" value={act} onChange={setAct} tabs={[{ id: "all", label: "All" }, ...["resell", "repair", "recycle", "donate"].map((a) => ({ id: a, label: ACTION_LABEL[a] }))]} />
        <label className="block"><span className="sr-only">Category</span><select className={`${inputCls} w-auto`} value={cat} onChange={(e) => setCat(e.target.value)}><option value="all">All categories</option>{cats.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label className="block"><span className="sr-only">Condition</span><select className={`${inputCls} w-auto`} value={cond} onChange={(e) => setCond(e.target.value)}><option value="all">Any condition</option>{conds.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
      </div>

      {rows.length === 0 ? (
        <Empty icon={<Store className="h-6 w-6" />} title="Nothing matches those filters" body="Try a different category or condition." action={<Button variant="outline" onClick={() => { setCat("all"); setCond("all"); setAct("all"); }}>Clear filters</Button>} />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((r: any) => (
            <li key={r.id}>
              <Card className="flex h-full flex-col">
                <div className="flex items-start justify-between gap-2"><h2 className="text-xl font-semibold leading-tight">{r.name}</h2><Badge tone={r.condition === "damaged" ? "alert" : "neutral"}>{r.condition_label}</Badge></div>
                <p className="text-sm text-ink-500">{r.category_label}</p>
                <dl className="mt-4 space-y-3">
                  <div><dt className="text-sm text-ink-500">Estimated resale</dt><dd className="font-display text-xl font-semibold tabular-nums">{r.resale ? inrRange(r.resale) : "Not resaleable"}</dd></div>
                  <div><dt className="text-sm text-ink-500">Recycling value</dt><dd className="font-display text-lg font-semibold tabular-nums text-ink-700">{inrRange(r.recycle)}</dd></div>
                </dl>
                <div className="mt-4 flex-1 rounded-xl bg-petrol-50 p-3"><Badge tone="petrol">{ACTION_LABEL[r.action.primary]}</Badge><p className="mt-1 font-medium text-petrol-700">{r.action.headline}</p><p className="text-sm text-ink-700">{r.action.reason}</p></div>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-3"><LinkButton to="/scan" variant="outline">Scan yours for a tailored estimate</LinkButton><span className="text-sm text-ink-500">Estimated range, not a guaranteed offer.</span></div>
    </div>
  );
}
