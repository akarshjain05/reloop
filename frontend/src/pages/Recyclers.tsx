import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ExternalLink, MapPin, Star } from "lucide-react";
import { Badge, Button, Card, Empty, ErrorBox, inputCls, LinkButton, Notice, PageHeader, PageSkeleton } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { cn } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function MapPanel({ origin, items, selected, onSelect }: { origin: { lat: number; lng: number }; items: any[]; selected?: string; onSelect: (id: string) => void }) {
  const W = 420, H = 340, pad = 34;
  const pts = [origin, ...items];
  const lats = pts.map((p) => p.lat), lngs = pts.map((p) => p.lng);
  const [minLa, maxLa, minLn, maxLn] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const sx = (lng: number) => pad + ((lng - minLn) / Math.max(1e-6, maxLn - minLn)) * (W - 2 * pad);
  const sy = (lat: number) => H - pad - ((lat - minLa) / Math.max(1e-6, maxLa - minLa)) * (H - 2 * pad);
  return (
    <figure className="overflow-hidden rounded-2xl border border-mist-200 bg-petrol-50">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="group" aria-label="Schematic map of nearby recycling locations">
        {[1, 2, 3, 4].map((i) => <line key={`h${i}`} x1={0} x2={W} y1={(H / 5) * i} y2={(H / 5) * i} stroke="#CFE6E7" strokeWidth="1" />)}
        {[1, 2, 3, 4, 5].map((i) => <line key={`v${i}`} y1={0} y2={H} x1={(W / 6) * i} x2={(W / 6) * i} stroke="#CFE6E7" strokeWidth="1" />)}
        <g aria-label="Your location"><circle cx={sx(origin.lng)} cy={sy(origin.lat)} r="16" fill="#0E5257" opacity=".15" /><circle cx={sx(origin.lng)} cy={sy(origin.lat)} r="7" fill="#0E5257" stroke="#fff" strokeWidth="3" /><text x={sx(origin.lng) + 12} y={sy(origin.lat) - 10} fontSize="12" fontWeight="600" fill="#0A3F43">You</text></g>
        {items.map((r, i) => {
          const on = selected === r.id, ok = r.verification.status !== "unverified";
          return (
            <g key={r.id} role="button" tabIndex={0} aria-label={`Location ${i + 1}: ${r.name}, ${r.distance_km} kilometres`} onClick={() => onSelect(r.id)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(r.id)} className="cursor-pointer outline-none focus-visible:[&>circle]:stroke-ink">
              <circle cx={sx(r.lng)} cy={sy(r.lat)} r={on ? 17 : 14} fill={on ? "#F5B83D" : ok ? "#14797F" : "#fff"} stroke={on ? "#0D1B1E" : "#0E5257"} strokeWidth="2.5" />
              <text x={sx(r.lng)} y={sy(r.lat) + 5} textAnchor="middle" fontSize="13" fontWeight="700" fill={on ? "#0D1B1E" : ok ? "#fff" : "#0E5257"}>{i + 1}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="px-3 py-2 text-xs text-ink-500">Schematic map of demo locations, not to scale. No map API is configured, so nothing here calls an external service.</figcaption>
    </figure>
  );
}

export default function Recyclers() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const sid = params.get("s");
  const options = useAsync(() => api.get("/waste/options"), []);
  const itemCat = useMemo(() => options.data?.items.find((i: any) => i.key === params.get("item"))?.category ?? "", [options.data, params]);
  const [cat, setCat] = useState<string | null>(null);
  const [service, setService] = useState("recycle");
  const [pickup, setPickup] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | undefined>();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const category = cat ?? itemCat;
  const qs = new URLSearchParams({ ...(category ? { category } : {}), ...(service ? { service } : {}), ...(pickup ? { pickup: "true" } : {}), ...(q ? { q } : {}) }).toString();
  const { data, error, loading, reload } = useAsync(() => api.get(`/recyclers?${qs}`), [qs]);
  const cats = useMemo(() => Array.from(new Map<string, string>((options.data?.items ?? []).map((i: any) => [i.category, i.category_label])).entries()), [options.data]);

  const dropoff = async (rid: string) => {
    setBusy(rid); setErr(null);
    try { await api.post("/pickups", { submission_ids: [sid], mode: "dropoff", recycler_id: rid }); nav("/pickup"); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Couldn't plan that drop-off."); } finally { setBusy(null); }
  };
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div>
      <PageHeader title="Find a recycler" subtitle="Nearby drop-off points and pickup services, sorted by distance from your building." />
      <Notice tone="signal"><strong>Demo data.</strong> {data?.notice ?? "These are fictional demo entries, not verified or officially authorised recyclers."}</Notice>
      <div className="my-4 flex flex-wrap items-center gap-3">
        <label><span className="sr-only">Accepted category</span><select className={`${inputCls} w-auto`} value={category} onChange={(e) => setCat(e.target.value)}><option value="">Any category</option>{cats.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label><span className="sr-only">Service</span><select className={`${inputCls} w-auto`} value={service} onChange={(e) => setService(e.target.value)}><option value="recycle">Recycle</option><option value="repair">Repair and resell</option><option value="">All services</option></select></label>
        <label className="flex h-11 items-center gap-2 rounded-xl border border-mist-300 bg-white px-3"><input type="checkbox" className="h-4 w-4 accent-[#0E5257]" checked={pickup} onChange={(e) => setPickup(e.target.checked)} />Pickup available</label>
        <label className="grow sm:grow-0"><span className="sr-only">Search</span><input className={`${inputCls} sm:w-56`} placeholder="Search by name or area" value={q} onChange={(e) => setQ(e.target.value)} /></label>
      </div>
      {err && <div className="mb-3"><Notice tone="alert">{err}</Notice></div>}
      {loading && !data ? <PageSkeleton /> : data.items.length === 0 ? (
        <Empty icon={<MapPin className="h-6 w-6" />} title="No locations match" body="Try removing a filter, or choose a different category." action={<Button variant="outline" onClick={() => { setCat(""); setService(""); setPickup(false); setQ(""); }}>Clear filters</Button>} />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
          <div className="lg:order-2 lg:sticky lg:top-24 lg:self-start"><MapPanel origin={data.origin} items={data.items} selected={sel} onSelect={setSel} /></div>
          <ul className="space-y-3 lg:order-1">
            {data.items.map((r: any, i: number) => (
              <li key={r.id}>
                <Card className={cn("transition", sel === r.id && "ring-2 ring-signal")} onClick={() => setSel(r.id)}>
                  <div className="flex items-start gap-3">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-petrol-600 text-sm font-bold text-white">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold leading-tight">{r.name}</h2><Badge tone={r.verification.status === "unverified" ? "neutral" : "petrol"}>{r.verification.label}</Badge></div>
                      <p className="text-sm text-ink-500">{r.address}</p>
                      <p className="mt-1 text-[15px]"><strong className="tabular-nums">{r.distance_km} km</strong> away, <span className="inline-flex items-center gap-0.5"><Star className="h-3.5 w-3.5 fill-signal text-signal" aria-hidden="true" /><span className="tabular-nums">{r.rating}</span></span>, {r.hours}</p>
                      <p className="mt-1 text-sm text-ink-700">{r.pickup_available ? `Pickup available from ${r.min_pickup_kg} kg.` : "Drop-off only."} About {r.processing_days} days to process.</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">{r.accepts_labels.slice(0, 4).map((a: string) => <Badge key={a}>{a}</Badge>)}{r.accepts_labels.length > 4 && <Badge>+{r.accepts_labels.length - 4} more</Badge>}</div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <a href={r.directions_url} target="_blank" rel="noopener noreferrer" className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-mist-300 bg-white px-3 text-sm font-medium hover:bg-mist-100">Directions<ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /><span className="sr-only"> (opens Google Maps)</span></a>
                        {sid ? <>
                          <Button size="sm" loading={busy === r.id} onClick={(e) => { e.stopPropagation(); dropoff(r.id); }}>Plan drop-off here</Button>
                          {r.pickup_available && <LinkButton to={`/pickup?s=${sid}&recycler=${r.id}`} size="sm" variant="outline">Schedule pickup</LinkButton>}
                        </> : <LinkButton to="/scan" size="sm" variant="outline">Scan an item to use it</LinkButton>}
                      </div>
                    </div>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
