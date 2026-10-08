import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, Package } from "lucide-react";
import { Reward } from "../components/Reward";
import { Badge, Button, Card, Empty, ErrorBox, Field, inputCls, LinkButton, Notice, PageHeader, PageSkeleton } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { cn, dateShort, kg, STATUS_TONE } from "../lib/format";
import { useRuntime } from "../lib/runtime";
import { useAsync } from "../lib/useAsync";

const STEPS = ["Items", "Where", "When", "Confirm"];

function Timeline({ p }: { p: any }) {
  const idx = p.steps.findIndex((s: any) => s.status === p.status);
  return (
    <ol className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Progress">
      {p.steps.map((s: any, i: number) => <li key={s.status} className={cn("flex items-center gap-1.5", i <= idx ? "font-medium text-petrol-700" : "text-ink-400")}><span className={cn("grid h-5 w-5 place-items-center rounded-full text-[10px]", i <= idx ? "bg-petrol-600 text-white" : "bg-mist-200")}>{i <= idx ? <Check className="h-3 w-3" aria-hidden="true" /> : i + 1}</span>{s.label}</li>)}
    </ol>
  );
}

export default function Pickup() {
  const [params] = useSearchParams();
  const { status } = useRuntime();
  const items = useAsync(() => api.get("/waste/history"), []);
  const mine = useAsync(() => api.get("/pickups"), []);
  const slots = useAsync(() => api.get("/pickups/slots"), []);
  const recs = useAsync(() => api.get("/recyclers?service=recycle"), []);
  const [step, setStep] = useState(0);
  const [sel, setSel] = useState<string[]>(params.get("s") ? [params.get("s")!] : []);
  const [mode, setMode] = useState<"pickup" | "dropoff">("pickup");
  const [addr, setAddr] = useState({ line: "", city: "Surat", pincode: "" });
  const [date, setDate] = useState("");
  const [slot, setSlot] = useState("");
  const [recycler, setRecycler] = useState(params.get("recycler") ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [created, setCreated] = useState<any>(null);
  const [reward, setReward] = useState<any>(null);

  const confirmed = useMemo(() => (items.data ?? []).filter((s: any) => s.status === "confirmed"), [items.data]);
  const chosen = confirmed.filter((s: any) => sel.includes(s.id));
  const totalKg = chosen.reduce((a: number, s: any) => a + s.estimate.impact.weight_kg, 0);
  const totalPts = chosen.reduce((a: number, s: any) => a + s.estimate.points.total, 0);
  const cats = new Set(chosen.map((s: any) => s.item.category));
  const dropCandidates = (recs.data?.items ?? []).filter((r: any) => [...cats].every((c) => r.accepts.includes(c)));
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i + 1); return { iso: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`, label: d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }) }; }), []);
  useEffect(() => { if (mode === "dropoff" && !recycler && dropCandidates[0]) setRecycler(dropCandidates[0].id); }, [mode, dropCandidates, recycler]);

  const canNext = [chosen.length > 0, mode === "dropoff" ? !!recycler : addr.line.trim().length >= 5 && addr.city.trim().length >= 2 && (!addr.pincode || /^\d{6}$/.test(addr.pincode)), mode === "dropoff" || (!!date && !!slot), true][step];
  const steps = mode === "dropoff" ? [0, 1, 3] : [0, 1, 2, 3];
  const pos = steps.indexOf(step);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const body: any = { submission_ids: sel, mode };
      if (mode === "pickup") Object.assign(body, { address: { line: addr.line, city: addr.city, pincode: addr.pincode || undefined }, date, slot, ...(recycler ? { recycler_id: recycler } : {}) });
      else body.recycler_id = recycler;
      setCreated(await api.post("/pickups", body)); mine.reload(); items.reload();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Couldn't create the request."); } finally { setBusy(false); }
  };
  const ff = async (id: string) => {
    setBusy(true); setErr(null);
    try { const p = await api.post(`/pickups/${id}/fast-forward`); setCreated(p); setReward(p.rewards); mine.reload(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  if (items.error) return <ErrorBox error={items.error} onRetry={items.reload} />;
  if (items.loading && !items.data) return <PageSkeleton />;
  const demo = status?.demo_mode;

  return (
    <div className="space-y-8">
      <PageHeader title="Pickups and drop-offs" subtitle="Choose items, say where and when, and a collector takes it from there. Points arrive once it's verified." />
      {created ? (
        <div className="space-y-4">
          <Card className="rounded-hero">
            <div className="flex items-center gap-2 text-ok"><Check className="h-5 w-5" aria-hidden="true" /><h2 className="text-2xl font-semibold">{created.mode === "dropoff" ? "Drop-off planned" : "Pickup requested"}</h2></div>
            <p className="mt-1 text-ink-700">{created.recycler_name}{created.mode === "pickup" ? `, ${dateShort(created.date)} between ${created.slot}` : ""}. {kg(created.total_kg)} across {created.items.length} item{created.items.length > 1 ? "s" : ""}.</p>
            {created.drop_code && <p className="mt-3 rounded-xl bg-signal-100 p-3 text-lg">Show this code at the counter: <strong className="font-display tracking-widest">{created.drop_code}</strong></p>}
            <div className="mt-4"><Timeline p={created} /></div>
            {demo && created.status !== "verified" && created.status !== "recycled" && (
              <div className="mt-5 rounded-xl border border-dashed border-petrol-200 bg-petrol-50 p-4"><p className="text-sm text-petrol-700"><strong>Demo shortcut.</strong> In real life a collector and verifier would do these steps (you can see that in Operations). Skip ahead to see what verification changes.</p>
                <Button className="mt-3" variant="signal" loading={busy} onClick={() => ff(created.id)}>Simulate collection and verification</Button></div>
            )}
            {err && <div className="mt-3"><Notice tone="alert">{err}</Notice></div>}
          </Card>
          {reward && <Reward rewards={reward} />}
          <div className="flex flex-wrap gap-3"><Button variant="outline" onClick={() => { setCreated(null); setReward(null); setSel([]); setStep(0); }}>Schedule another</Button><LinkButton to="/dashboard" variant="outline">Back to home</LinkButton><LinkButton to="/leaderboard" variant="outline">See the leaderboard</LinkButton></div>
        </div>
      ) : confirmed.length === 0 ? (
        <Empty icon={<Package className="h-6 w-6" />} title="No confirmed items yet" body="Scan an item and confirm what it is, then come back to schedule it." action={<LinkButton to="/scan" variant="signal">Scan an item</LinkButton>} />
      ) : (
        <Card className="rounded-hero p-5 sm:p-7">
          <ol className="mb-6 flex gap-2" aria-label="Steps">{steps.map((s, i) => <li key={s} aria-current={s === step ? "step" : undefined} className={cn("flex-1 border-t-4 pt-2 text-sm font-medium", i <= pos ? "border-petrol-600 text-petrol-700" : "border-mist-200 text-ink-400")}>{i + 1}. {STEPS[s]}</li>)}</ol>
          {step === 0 && (
            <div>
              <h2 className="text-2xl font-semibold">Which items?</h2>
              <ul className="mt-3 space-y-2">{confirmed.map((s: any) => (
                <li key={s.id}><label className={cn("flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border p-3", sel.includes(s.id) ? "border-petrol-500 bg-petrol-50" : "border-mist-200")}>
                  <input type="checkbox" className="h-5 w-5 accent-[#0E5257]" checked={sel.includes(s.id)} onChange={(e) => setSel(e.target.checked ? [...sel, s.id] : sel.filter((x) => x !== s.id))} />
                  <span className="min-w-0 flex-1"><span className="block font-medium">{s.item.quantity > 1 ? `${s.item.quantity} × ` : ""}{s.item.label}</span><span className="text-sm text-ink-500">{kg(s.estimate.impact.weight_kg)}, about {s.estimate.points.total} points once verified</span></span>
                </label></li>))}</ul>
              <fieldset className="mt-5"><legend className="text-sm font-medium text-ink-700">How do you want to hand it over?</legend>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">{([["pickup", "Pick it up from my address", "A collector comes to you."], ["dropoff", "I'll drop it off", "Take it to a nearby recycler and show a code."]] as const).map(([k, t, d]) => (
                  <label key={k} className={cn("flex cursor-pointer gap-3 rounded-xl border p-3", mode === k ? "border-petrol-500 bg-petrol-50" : "border-mist-200")}><input type="radio" name="mode" className="mt-1 h-4 w-4 accent-[#0E5257]" checked={mode === k} onChange={() => setMode(k)} /><span><span className="block font-medium">{t}</span><span className="text-sm text-ink-500">{d}</span></span></label>))}</div></fieldset>
              {chosen.length > 0 && <p className="mt-4 text-[15px]">Selected: <strong>{kg(totalKg)}</strong>, about <strong>{totalPts} points</strong> once verified (estimate).</p>}
            </div>
          )}
          {step === 1 && mode === "pickup" && (
            <div><h2 className="text-2xl font-semibold">Where should we collect from?</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="sm:col-span-2"><Field label="Address"><input className={inputCls} value={addr.line} onChange={(e) => setAddr({ ...addr, line: e.target.value })} placeholder="Room, block, street" autoComplete="street-address" /></Field></div>
                <Field label="City"><input className={inputCls} value={addr.city} onChange={(e) => setAddr({ ...addr, city: e.target.value })} autoComplete="address-level2" /></Field>
                <Field label="Pincode (optional)"><input className={inputCls} inputMode="numeric" maxLength={6} value={addr.pincode} onChange={(e) => setAddr({ ...addr, pincode: e.target.value })} autoComplete="postal-code" /></Field></div></div>
          )}
          {step === 1 && mode === "dropoff" && (
            <div><h2 className="text-2xl font-semibold">Where will you drop it off?</h2>
              {dropCandidates.length === 0 ? <div className="mt-3"><Notice tone="signal">No nearby recycler accepts all of these items together. Try splitting them into separate requests.</Notice></div> : (
                <ul className="mt-3 space-y-2">{dropCandidates.map((r: any) => <li key={r.id}><label className={cn("flex cursor-pointer gap-3 rounded-xl border p-3", recycler === r.id ? "border-petrol-500 bg-petrol-50" : "border-mist-200")}><input type="radio" name="rec" className="mt-1 h-4 w-4 accent-[#0E5257]" checked={recycler === r.id} onChange={() => setRecycler(r.id)} /><span><span className="block font-medium">{r.name}</span><span className="text-sm text-ink-500">{r.distance_km} km, {r.hours}. {r.verification.label}.</span></span></label></li>)}</ul>)}</div>
          )}
          {step === 2 && (
            <div><h2 className="text-2xl font-semibold">When works for you?</h2>
              <div className="mt-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Date">{days.map((d) => <button key={d.iso} role="radio" aria-checked={date === d.iso} onClick={() => setDate(d.iso)} className={cn("h-11 rounded-xl border px-4 text-sm font-medium", date === d.iso ? "border-petrol-600 bg-petrol-600 text-white" : "border-mist-300 bg-white hover:bg-mist-100")}>{d.label}</button>)}</div>
              <div className="mt-4 flex flex-wrap gap-2" role="radiogroup" aria-label="Time slot">{(slots.data?.slots ?? []).map((s: string) => <button key={s} role="radio" aria-checked={slot === s} onClick={() => setSlot(s)} className={cn("h-11 rounded-xl border px-4 text-sm font-medium tabular-nums", slot === s ? "border-petrol-600 bg-petrol-600 text-white" : "border-mist-300 bg-white hover:bg-mist-100")}>{s}</button>)}</div></div>
          )}
          {step === 3 && (
            <div><h2 className="text-2xl font-semibold">Check and confirm</h2>
              <dl className="mt-3 divide-y divide-mist-200 rounded-xl border border-mist-200">
                {[["Items", chosen.map((s: any) => `${s.item.quantity > 1 ? s.item.quantity + " × " : ""}${s.item.label}`).join(", ")], ["Weight", `${kg(totalKg)} (estimate)`], ["Handover", mode === "pickup" ? `Pickup at ${addr.line}, ${addr.city}` : `Drop-off at ${dropCandidates.find((r: any) => r.id === recycler)?.name ?? ""}`], ...(mode === "pickup" ? [["When", `${days.find((d) => d.iso === date)?.label}, ${slot}`]] : []), ["Points once verified", `about ${totalPts} (estimate)`]].map(([k, v]) => <div key={k} className="flex justify-between gap-4 p-3"><dt className="text-ink-500">{k}</dt><dd className="text-right font-medium">{v}</dd></div>)}
              </dl>
              {mode === "pickup" && <p className="mt-3 text-sm text-ink-500">We assign the nearest verified-in-demo recycler that can take these items{recycler ? "" : " and meets its minimum pickup weight"}.</p>}
              {err && <div className="mt-3"><Notice tone="alert">{err}</Notice></div>}
            </div>
          )}
          <div className="mt-6 flex gap-3">
            {pos > 0 && <Button variant="outline" size="lg" onClick={() => setStep(steps[pos - 1])}>Back</Button>}
            {step !== 3 ? <Button size="lg" disabled={!canNext} onClick={() => setStep(steps[pos + 1])}>Continue</Button> : <Button size="lg" variant="signal" loading={busy} onClick={submit}>Confirm request</Button>}
          </div>
        </Card>
      )}

      <section aria-labelledby="mine">
        <h2 id="mine" className="mb-3 text-2xl font-semibold">Your requests</h2>
        {mine.error ? <ErrorBox error={mine.error} onRetry={mine.reload} /> : !mine.data || mine.data.length === 0 ? <Empty title="No requests yet" body="Requests you make show up here with their progress." /> : (
          <ul className="space-y-3">{mine.data.map((p: any) => (
            <li key={p.id}><Card>
              <div className="flex flex-wrap items-center justify-between gap-2"><div><span className="font-semibold">{p.items.map((i: any) => i.label).join(", ")}</span><span className="text-ink-500">, {p.recycler_name}</span></div><Badge tone={STATUS_TONE[p.status]}>{p.status_label}</Badge></div>
              <p className="text-sm text-ink-500">{p.mode === "pickup" ? `${dateShort(p.date)}, ${p.slot}` : `Drop-off code ${p.drop_code}`}. {kg(p.total_kg)}.{p.collector_name ? ` Collector: ${p.collector_name}.` : ""}</p>
              <div className="mt-3"><Timeline p={p} /></div>
              {demo && !["verified", "recycled", "cancelled"].includes(p.status) && <Button className="mt-3" size="sm" variant="outline" loading={busy} onClick={() => ff(p.id)}>Demo: simulate collection and verification</Button>}
              {p.rewards && <p className="mt-3 rounded-lg bg-ok-100 p-2 text-sm text-ok">Verified: +{p.rewards.points} points, {kg(p.rewards.kg)} diverted.</p>}
            </Card></li>))}</ul>
        )}
      </section>
    </div>
  );
}
