export const cn = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
// Currency symbol and number locale come from the backend settings (CURRENCY_SYMBOL / LOCALE) via setLocale().
let L = { symbol: "₹", locale: "en-IN" };
export const setLocale = (x: Partial<typeof L>) => { L = { ...L, ...x }; };
export const num = (n: number | null | undefined, d = 0) => (n == null ? "–" : new Intl.NumberFormat(L.locale, { maximumFractionDigits: d, minimumFractionDigits: 0 }).format(n));
export const inr = (n: number | null | undefined) => (n == null ? "–" : `${L.symbol}${new Intl.NumberFormat(L.locale).format(Math.round(n))}`);
export const inrRange = (r?: { min: number; max: number } | null) => (r ? `${inr(r.min)} – ${inr(r.max)}` : "Not resaleable");
export const kg = (n: number | null | undefined, d = 1) => (n == null ? "–" : `${num(n, d)} kg`);
export const pct = (v: number, d = 0) => `${(v * 100).toFixed(d)}%`;
export function dateShort(iso?: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
export function timeAgo(iso?: string) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return dateShort(iso);
}
export const monthLabel = (ym: string) => new Date(`${ym}-01T00:00:00`).toLocaleDateString("en-IN", { month: "short" });
export const ACTION_LABEL: Record<string, string> = { resell: "Resell", repair: "Repair", recycle: "Recycle", donate: "Donate" };
export const STATUS_TONE: Record<string, string> = { requested: "neutral", scheduled: "petrol", collector_assigned: "petrol", picked_up: "signal", verified: "ok", recycled: "ok", cancelled: "alert" };
