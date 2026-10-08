import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Camera, Check, Loader2, Recycle, ScanLine, ShieldCheck, Upload } from "lucide-react";
import { Badge, Button, Card, Disclosure, EstimateChip, Field, inputCls, Notice, PageHeader, ProgressBar, Tabs } from "../components/ui";
import { api, ApiError, resizeImage } from "../lib/api";
import { ACTION_LABEL, cn, inr, inrRange, kg, num } from "../lib/format";
import { useRuntime } from "../lib/runtime";
import { useAsync } from "../lib/useAsync";

const STEPS = ["Identifying object", "Checking category", "Estimating value", "Calculating impact", "Finding best action"];
const SAMPLES = [{ file: "laptop.jpg", label: "Laptop" }, { file: "phone.jpg", label: "Phone" }, { file: "charger.jpg", label: "Charger" }, { file: "power-bank.jpg", label: "Power bank" }];
const MIN_MS = import.meta.env.MODE === "test" ? 0 : 1; // analysis steps stay visible for a moment in the real UI
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms * MIN_MS));

async function sampleFile(name: string): Promise<File> {
  const blob = await (await fetch(`/samples/${name}`)).blob();
  return new File([blob], name, { type: "image/jpeg" });
}

function DropZone({ onFile, busy, hint, children }: { onFile: (f: File) => void; busy?: boolean; hint?: string; children?: React.ReactNode }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const pick = (e: ChangeEvent<HTMLInputElement>) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; };
  const drop = (e: DragEvent) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); };
  return (
    <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}
      className={cn("rounded-hero border-2 border-dashed bg-white p-6 text-center transition sm:p-10", over ? "border-petrol-500 bg-petrol-50" : "border-mist-300")}>
      <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-petrol-50 text-petrol-600"><ScanLine className="h-8 w-8" aria-hidden="true" /></div>
      <h2 className="mt-4 text-2xl font-semibold">Point your camera at it</h2>
      <p className="mx-auto mt-1 max-w-md text-ink-500">{hint ?? "A clear, well-lit photo of one item works best. We'll tell you what it is, what it's worth and the best next step."}</p>
      <input ref={input} type="file" accept="image/*" capture="environment" className="sr-only" aria-label="Take or choose a photo" onChange={pick} disabled={busy} data-testid="photo-input" />
      <div className="mt-5 flex flex-wrap justify-center gap-3">
        <Button size="lg" variant="signal" onClick={() => input.current?.click()} disabled={busy}><Camera className="h-5 w-5" aria-hidden="true" />Take or choose a photo</Button>
      </div>
      {children}
    </div>
  );
}

function AnalysisSteps() {
  const [active, setActive] = useState(0);
  useEffect(() => { const t = setInterval(() => setActive((a) => Math.min(a + 1, STEPS.length - 1)), 480); return () => clearInterval(t); }, []);
  return (
    <Card className="mx-auto max-w-lg rounded-hero p-8" aria-live="polite">
      <h2 className="text-2xl font-semibold">Analyzing your item…</h2>
      <ol className="mt-5 space-y-3">
        {STEPS.map((s, i) => (
          <li key={s} className={cn("flex items-center gap-3 text-[15px]", i > active && "text-ink-400")}>
            <span className={cn("grid h-6 w-6 place-items-center rounded-full", i < active ? "bg-ok text-white" : i === active ? "bg-petrol-100 text-petrol-700" : "bg-mist-200")}>
              {i < active ? <Check className="h-4 w-4" aria-hidden="true" /> : i === active ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            </span>
            <span className={i === active ? "font-medium text-ink" : ""}>{s}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function Fact({ label, children, sub }: { label: string; children: React.ReactNode; sub?: React.ReactNode }) {
  return <div className="rounded-xl bg-mist-50 p-3"><div className="text-sm text-ink-500">{label}</div><div className="font-display text-xl font-semibold leading-snug">{children}</div>{sub && <div className="text-xs text-ink-500">{sub}</div>}</div>;
}

function CorrectionForm({ sub, options, saving, onSave, onCancel }: { sub: any; options: any; saving: boolean; onSave: (c: any) => void; onCancel: () => void }) {
  const [f, setF] = useState({ item_type: sub.item.item_type, condition: sub.item.condition, brand: sub.item.brand ?? "", quantity: sub.item.quantity, weight_kg: sub.item.weight_kg ?? "" });
  const set = (k: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = () => onSave({ item_type: f.item_type, condition: f.condition, brand: f.brand || undefined, quantity: Number(f.quantity) || 1, weight_kg: f.weight_kg === "" ? undefined : Number(f.weight_kg) });
  return (
    <Card tone="mist" aria-label="Correct the result">
      <h3 className="text-lg font-semibold">Correct the result</h3>
      <p className="text-sm text-ink-500">You know your item better than the AI. Your corrections update the estimate and help us measure how accurate the AI is.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Field label="Item"><select className={inputCls} value={f.item_type} onChange={set("item_type")}>{options?.items.map((o: any) => <option key={o.key} value={o.key}>{o.label}</option>)}</select></Field>
        <Field label="Condition"><select className={inputCls} value={f.condition} onChange={set("condition")}>{options?.conditions.map((o: any) => <option key={o.key} value={o.key}>{o.label}</option>)}</select></Field>
        <Field label="Brand (optional)"><input className={inputCls} value={f.brand} onChange={set("brand")} maxLength={40} placeholder="For example Dell" /></Field>
        <Field label="Quantity"><input className={inputCls} type="number" min={1} max={50} value={f.quantity} onChange={set("quantity")} /></Field>
        <Field label="Approximate weight of one item (kg)" hint="Leave blank to use the typical weight."><input className={inputCls} type="number" min={0.01} max={100} step={0.01} value={f.weight_kg} onChange={set("weight_kg")} /></Field>
      </div>
      <div className="mt-4 flex gap-3"><Button onClick={submit} loading={saving}>Update estimate</Button><Button variant="ghost" onClick={onCancel}>Cancel</Button></div>
    </Card>
  );
}

function ItemScanner() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { setProof } = useRuntime();
  const options = useAsync(() => api.get("/waste/options"), []);
  const [phase, setPhase] = useState<"idle" | "analyzing" | "result">("idle");
  const [preview, setPreview] = useState<string>("");
  const [hint, setHint] = useState("");
  const [sub, setSub] = useState<any>(null);
  const [aiStatus, setAiStatus] = useState("ok");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [correcting, setCorrecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [updated, setUpdated] = useState(false);
  const [hintText, setHintText] = useState<string | null>(null);
  const [choice, setChoice] = useState<string | null>(null);

  const load = (s: any) => { setSub(s); setPhase("result"); setPreview(api.mediaUrl(s.image_url)); };
  useEffect(() => { const id = params.get("resume"); if (id) api.get(`/waste/${id}`).then(load, () => {}); }, [params]);

  const start = async (file: File) => {
    setError(null); setUpdated(false); setChoice(null); setHintText(null); setCorrecting(false);
    setPreview(URL.createObjectURL(file)); setPhase("analyzing");
    try {
      const small = await resizeImage(file);
      const [res] = await Promise.all([api.upload("/waste/analyze", small, { hint }), wait(2400)]);
      if (!res.submission) { setError(res.message); setPhase("idle"); return; }
      setAiStatus(res.ai_status); setMessage(res.message); setSub(res.submission); setProof(res.submission.aws);
      setCorrecting(res.ai_status === "unavailable"); setPhase("result");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again."); setPhase("idle");
    }
  };

  const confirm = async (corrections?: any) => {
    setSaving(true); setError(null);
    try {
      const s = await api.post("/waste/confirm", { submission_id: sub.id, corrections });
      setSub(s); setUpdated(!!corrections); setCorrecting(false);
      return s;
    } catch (e) { setError(e instanceof ApiError ? e.message : "Couldn't save. Please try again."); return null; } finally { setSaving(false); }
  };
  const ensureConfirmed = async () => (sub.status === "analyzed" ? await confirm() : sub);
  const choose = async (a: string) => {
    const s = await ensureConfirmed(); if (!s) return;
    try { const r = await api.post(`/waste/${s.id}/action`, { action: a }); setChoice(a); setHintText(r.action_hint); } catch (e) { setError((e as Error).message); }
  };
  const go = async (path: string) => { const s = await ensureConfirmed(); if (s) nav(`${path}${path.includes("?") ? "&" : "?"}s=${s.id}&item=${s.item.item_type}`); };

  if (phase === "analyzing") return <div className="space-y-4">{preview && <img src={preview} alt="Your photo being analyzed" className="mx-auto h-40 w-40 rounded-2xl object-cover" />}<AnalysisSteps /></div>;
  if (phase === "idle")
    return (
      <div className="space-y-4">
        {error && <Notice tone="alert"><AlertTriangle className="mr-1 inline h-4 w-4" aria-hidden="true" />{error}</Notice>}
        <DropZone onFile={start}>
          <div className="mx-auto mt-6 max-w-md text-left"><Field label="What is it? (optional)" hint="A hint helps when the photo is unclear."><input className={inputCls} value={hint} onChange={(e) => setHint(e.target.value)} maxLength={40} placeholder="For example old laptop" /></Field></div>
          <div className="mt-6"><p className="text-sm text-ink-500">No photo handy? Try a sample.</p>
            <div className="mt-2 flex flex-wrap justify-center gap-2">{SAMPLES.map((s) => <Button key={s.file} variant="outline" size="sm" onClick={async () => start(await sampleFile(s.file))}>{s.label}</Button>)}</div>
          </div>
        </DropZone>
      </div>
    );

  const it = sub.item, est = sub.estimate, sum = est.summary, act = est.action, flagged = sub.fraud?.status === "pending_review";
  const confirmed = sub.status === "confirmed" || sub.status === "pickup_requested";
  const lowConf = it.confidence > 0 && it.confidence < 0.7;
  return (
    <div className="space-y-4">
      {aiStatus === "fallback" && <Notice tone="signal">{message}</Notice>}
      {aiStatus === "unavailable" && <Notice tone="signal">{message}</Notice>}
      {flagged && <Notice tone="alert"><strong>Suspicious submission detected.</strong> Reason: {sub.fraud.flags?.[0]?.detail ?? "needs a manual check"} Status: pending verification, so points are held until it's reviewed.</Notice>}
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <div className="space-y-3">
          {preview && <img src={preview} alt={`Photo of your ${it.label.toLowerCase()}`} className="aspect-square w-full rounded-hero object-cover" />}
          <Button variant="outline" className="w-full" onClick={() => { setPhase("idle"); setSub(null); }}><Camera className="h-4 w-4" aria-hidden="true" />Scan something else</Button>
        </div>
        <Card className="rounded-hero p-6">
          <div className="flex flex-wrap items-center gap-2"><Badge tone="petrol">{it.source === "manual" ? "Chosen by you" : "Likely identified"}</Badge><EstimateChip>AI estimate</EstimateChip>{updated && <Badge tone="ok">Updated with your corrections</Badge>}</div>
          <h2 className="mt-2 text-4xl font-semibold">{it.quantity > 1 ? `${it.quantity} × ` : ""}{it.label}</h2>
          <p className="text-ink-500">{sub.category_label}{it.brand ? `, ${it.brand}` : ""}</p>
          {it.confidence > 0 && <div className="mt-3 max-w-sm"><div className="mb-1 flex justify-between text-sm"><span>Confidence</span><span className="font-semibold tabular-nums">{Math.round(it.confidence * 100)}%</span></div><ProgressBar pct={it.confidence * 100} tone={lowConf ? "signal" : "petrol"} label="AI confidence" />{lowConf && <p className="mt-1 text-sm text-[#7A5200]">Low confidence. Please check the item before confirming.</p>}</div>}
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Fact label="Condition">{sum.condition}</Fact>
            <Fact label={sum.value_basis === "recycle" ? "Estimated recycling value" : "Estimated resale value"} sub={est.value.label}>{inrRange({ min: sum.estimated_value_min, max: sum.estimated_value_max })}</Fact>
            <Fact label="Estimated weight">{kg(sum.estimated_weight_kg)}</Fact>
            <Fact label="Potential impact" sub="Illustrative, from configured impact factors">~{num(sum.estimated_co2_avoidance_kg, 1)} kg CO₂e avoided</Fact>
          </div>
          <div className="mt-5 rounded-2xl border border-petrol-200 bg-petrol-50 p-4">
            <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold text-petrol-700">Recommended action</span><Badge tone="petrol">{ACTION_LABEL[act.primary]}</Badge>{act.fallback && <Badge tone="neutral">else {ACTION_LABEL[act.fallback].toLowerCase()}</Badge>}</div>
            <p className="mt-1 font-display text-xl font-semibold">{act.headline}</p>
            <p className="text-sm text-ink-700">{act.reason}</p>
            {act.next_step && <p className="mt-2 text-sm text-petrol-700">{act.next_step.detail}</p>}
          </div>
          <p className="mt-4 text-[15px]">Recycle it through a verified pickup or drop-off to earn about <strong>{est.points.total} ReLoop points</strong>.</p>
          <div className="mt-2"><Disclosure summary="How points are calculated"><ul className="space-y-1">{est.points.breakdown.map((b: any, i: number) => <li key={i} className="flex justify-between gap-3"><span>{b.label}{b.detail ? ` (${b.detail})` : ""}</span><span className="tabular-nums">{b.points}</span></li>)}</ul></Disclosure></div>
          <p className="mt-4 text-sm text-ink-500">AI estimate — confirm item and condition for a more accurate value. {est.value.disclaimer} Impact is an estimate based on configured impact factors.</p>
        </Card>
      </div>

      {correcting && options.data && <CorrectionForm sub={sub} options={options.data} saving={saving} onSave={(c) => confirm(c)} onCancel={() => setCorrecting(false)} />}
      {error && <Notice tone="alert">{error}</Notice>}

      {!confirmed ? (
        <div className="flex flex-wrap gap-3">
          <Button size="lg" variant="signal" loading={saving} onClick={() => confirm()}><ShieldCheck className="h-5 w-5" aria-hidden="true" />Confirm</Button>
          <Button size="lg" variant="outline" onClick={() => setCorrecting((c) => !c)}>Correct result</Button>
          <Button size="lg" variant="outline" onClick={() => go("/recyclers")}>Find recycler</Button>
          <Button size="lg" variant="outline" onClick={() => go("/pickup")}>Schedule pickup</Button>
        </div>
      ) : (
        <Card className="rounded-hero">
          <div className="flex items-center gap-2 text-ok"><Check className="h-5 w-5" aria-hidden="true" /><h3 className="text-lg font-semibold">Confirmed. What would you like to do with it?</h3></div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(["recycle", "resell", "repair", "donate"] as const).map((a) => (
              <Button key={a} variant={choice === a ? "primary" : a === act.primary ? "signal" : "outline"} onClick={() => choose(a)} aria-pressed={choice === a}>{a === "recycle" && <Recycle className="h-4 w-4" aria-hidden="true" />}{ACTION_LABEL[a]}</Button>
            ))}
          </div>
          {hintText && <p className="mt-3 text-[15px] text-ink-700">{hintText}</p>}
          {(choice === "recycle" || sub.status === "pickup_requested") && sub.status !== "pickup_requested" && <div className="mt-3 flex flex-wrap gap-3"><Button onClick={() => go("/pickup")}>Schedule pickup</Button><Button variant="outline" onClick={() => go("/recyclers")}>Find recycler</Button></div>}
          {sub.status === "pickup_requested" && <p className="mt-3 text-sm text-ink-500">This item is already part of a pickup or drop-off request.</p>}
          <div className="mt-3"><Button variant="ghost" size="sm" onClick={() => setCorrecting((c) => !c)}>Edit details</Button></div>
        </Card>
      )}

      <Disclosure summary={`What ReLoop's agent did (${sub.agent.mode === "strands" ? "Strands Agents SDK on Amazon Bedrock" : sub.agent.mode === "manual" ? "manual selection" : "fixed tool pipeline"})`}>
        {sub.agent.summary && <p className="mb-3 rounded-lg bg-white p-3"><span className="font-medium">Summary ({sub.agent.mode === "strands" ? "model-written" : "rule-based"}): </span>{sub.agent.summary}</p>}
        <ol className="space-y-2">{sub.trace.map((t: any, i: number) => <li key={i} className="flex flex-wrap items-baseline gap-x-2"><code className="rounded bg-white px-1.5 py-0.5 text-xs">{t.tool}</code><span>{t.summary}</span><span className="text-xs text-ink-400">{t.ms} ms</span></li>)}</ol>
        <p className="mt-3 text-xs text-ink-500">Every number above comes from a tool call, not free-form model text. Price and impact tools read configured data files.</p>
      </Disclosure>
    </div>
  );
}

function BinScanner() {
  const { setProof } = useRuntime();
  const [phase, setPhase] = useState<"idle" | "busy" | "result" | "done">("idle");
  const [scan, setScan] = useState<any>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [done, setDone] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const start = async (f: File) => {
    setError(null); setPhase("busy");
    try { const [r] = await Promise.all([api.upload("/waste/bin-scan", await resizeImage(f)), wait(1800)]); setScan(r); setRemoved([]); setPhase("result"); } catch (e) { setError((e as Error).message); setPhase("idle"); }
  };
  const flagged = scan?.categories.filter((c: any) => c.status === "warn") ?? [];
  const confirm = async () => {
    try { setDone(await api.post(`/waste/bin-scan/${scan.id}/confirm`, { removed })); setPhase("done"); } catch (e) { setError((e as Error).message); }
  };
  if (phase === "busy") return <Card className="mx-auto max-w-lg rounded-hero p-8" aria-live="polite"><h2 className="flex items-center gap-2 text-2xl font-semibold"><Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />Reading your bin…</h2></Card>;
  if (phase === "idle")
    return (
      <div className="space-y-4">{error && <Notice tone="alert">{error}</Notice>}
        <DropZone onFile={start} hint="Photograph a mixed bin or pile. We'll flag e-waste and hazardous items so they don't end up in general waste.">
          <div className="mt-5"><Button variant="outline" size="sm" onClick={async () => start(await sampleFile("mixed-bin.jpg"))}>Try the sample bin</Button></div>
        </DropZone>
      </div>
    );
  return (
    <div className="space-y-4">
      <Card className="rounded-hero">
        <div className="flex flex-wrap items-center gap-2"><h2 className="text-2xl font-semibold">What we can see</h2><EstimateChip>AI estimate</EstimateChip>{scan.provider === "mock" && <Badge>Demo AI</Badge>}</div>
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {scan.categories.map((c: any) => (
            <li key={c.key} className={cn("rounded-xl border p-3", c.status === "warn" ? "border-signal bg-signal-100" : c.status === "ok" ? "border-ok/30 bg-ok-100" : c.status === "fixed" ? "border-ok/30 bg-ok-100" : "border-mist-200 bg-mist-50 text-ink-400")}>
              <div className="flex items-center gap-2 font-semibold">{c.status === "warn" ? <AlertTriangle className="h-4 w-4 text-[#7A5200]" aria-hidden="true" /> : c.present ? <Check className="h-4 w-4 text-ok" aria-hidden="true" /> : null}{c.label}</div>
              <div className="text-xs">{c.status === "warn" ? "Needs attention" : c.status === "fixed" ? "Taken out" : c.present ? "Looks right" : "Not seen"}</div>
              {c.note && <div className="mt-1 text-xs text-ink-700">{c.note}</div>}
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-xl bg-mist-50 p-3 text-[15px]">{scan.advice}</p>
        {phase === "result" && flagged.length > 0 && (
          <fieldset className="mt-4"><legend className="text-sm font-semibold">Did you take them out before disposal?</legend>
            {flagged.map((c: any) => <label key={c.key} className="mt-2 flex min-h-11 items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[#0E5257]" checked={removed.includes(c.key)} onChange={(e) => setRemoved(e.target.checked ? [...removed, c.key] : removed.filter((k) => k !== c.key))} />I've taken out the {c.label.toLowerCase()} items</label>)}
          </fieldset>
        )}
        {error && <div className="mt-3"><Notice tone="alert">{error}</Notice></div>}
        {phase === "result" && <div className="mt-4 flex gap-3"><Button variant="signal" size="lg" onClick={confirm}>Confirm and update my building</Button><Button variant="ghost" onClick={() => setPhase("idle")}>Scan again</Button></div>}
      </Card>
      {phase === "done" && done && (
        <Card tone="petrol" className="rounded-hero animate-pop">
          <h3 className="text-xl font-semibold">Thanks, that helps your building.</h3>
          <p className="mt-1">{done.points_awarded ? `+${done.points_awarded} points for checking your bin. ` : "Points for bin checks are limited to once a day. "}{done.building_score_before != null && <>Building ReLoop Score: {done.building_score_before} → {done.building_score_after}.</>}</p>
        </Card>
      )}
    </div>
  );
}

export default function Scan() {
  const [tab, setTab] = useState<"item" | "bin">("item");
  return (
    <div>
      <PageHeader title="WasteLens" subtitle="Photograph it, confirm what we saw, and we'll work out what it's worth and what to do next." actions={<Tabs label="What to scan" value={tab} onChange={setTab} tabs={[{ id: "item", label: "Scan an item" }, { id: "bin", label: "Scan my waste" }]} />} />
      {tab === "item" ? <ItemScanner /> : <BinScanner />}
    </div>
  );
}
