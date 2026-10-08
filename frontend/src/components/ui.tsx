import { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, LinkProps } from "react-router-dom";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { cn } from "../lib/format";

const base = "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol-600 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50";
const variants = {
  primary: "bg-petrol-600 text-white hover:bg-petrol-700",
  signal: "bg-signal font-semibold text-ink hover:bg-signal-600",
  outline: "border border-mist-300 bg-white text-ink hover:bg-mist-100",
  ghost: "text-ink-700 hover:bg-mist-200",
  danger: "bg-alert text-white hover:opacity-90",
};
const sizes = { sm: "h-9 px-3 text-sm", md: "h-11 px-4 text-[15px]", lg: "h-12 px-6 text-base" };
type Variant = keyof typeof variants;
type Size = keyof typeof sizes;

export const btn = (variant: Variant = "primary", size: Size = "md", className?: string) => cn(base, variants[variant], sizes[size], className);

export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean }) {
  return (
    <button {...rest} disabled={disabled || loading} className={cn(base, variants[variant], sizes[size], className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}
export function LinkButton({ variant = "primary", size = "md", className, children, ...rest }: LinkProps & { variant?: Variant; size?: Size }) {
  return <Link {...rest} className={cn(base, variants[variant], sizes[size], className)}>{children}</Link>;
}

export function Card({ className, children, tone = "white", ...rest }: { className?: string; children: ReactNode; tone?: "white" | "petrol" | "mist" } & React.HTMLAttributes<HTMLElement>) {
  const tones = { white: "bg-white border border-mist-200", mist: "bg-mist-50 border border-mist-200", petrol: "bg-petrol-700 text-white" };
  return <section {...rest} className={cn("rounded-2xl p-5", tones[tone], className)}>{children}</section>;
}

const badgeTones: Record<string, string> = {
  neutral: "bg-mist-200 text-ink-700", petrol: "bg-petrol-100 text-petrol-700", signal: "bg-signal-100 text-[#6E4A00]",
  ok: "bg-ok-100 text-ok", alert: "bg-alert-100 text-alert", copper: "bg-copper-100 text-copper",
};
export function Badge({ tone = "neutral", children, className }: { tone?: string; children: ReactNode; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", badgeTones[tone] ?? badgeTones.neutral, className)}>{children}</span>;
}
/** Marks every AI- or assumption-derived number so nothing reads as a measured fact. */
export const EstimateChip = ({ children = "AI estimate" }: { children?: ReactNode }) => <Badge tone="signal">{children}</Badge>;

export function Stat({ label, value, sub, className }: { label: string; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <div className="text-sm text-ink-500">{label}</div>
      <div className="font-display text-3xl font-semibold tabular-nums leading-tight">{value}</div>
      {sub && <div className="mt-0.5 text-sm text-ink-500">{sub}</div>}
    </div>
  );
}

export function ProgressBar({ pct, tone = "petrol", label }: { pct: number; tone?: "petrol" | "signal" | "copper" | "ok"; label?: string }) {
  const colors = { petrol: "bg-petrol-600", signal: "bg-signal", copper: "bg-copper", ok: "bg-ok" };
  const v = Math.max(0, Math.min(100, pct));
  return (
    <div role="progressbar" aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100} aria-label={label} className="h-2.5 w-full overflow-hidden rounded-full bg-mist-200">
      <div className={cn("h-full rounded-full transition-all duration-700", colors[tone])} style={{ width: `${v}%` }} />
    </div>
  );
}

export function Ring({ pct, size = 96, stroke = 10, children, color = "#0E5257" }: { pct: number; size?: number; stroke?: number; children?: ReactNode; color?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(100, pct)) / 100);
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#E1E8EA" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off} style={{ transition: "stroke-dashoffset .9s ease" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}

export const Skeleton = ({ className }: { className?: string }) => <div aria-hidden="true" className={cn("animate-pulse rounded-lg bg-mist-200", className)} />;
export function PageSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="space-y-4">
      <Skeleton className="h-10 w-64" /><Skeleton className="h-40 w-full" />
      <div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
    </div>
  );
}

export function Empty({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-mist-300 bg-white px-6 py-10 text-center">
      {icon && <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-petrol-50 text-petrol-600">{icon}</div>}
      <h3 className="text-lg font-semibold">{title}</h3>
      {body && <p className="mx-auto mt-1 max-w-sm text-ink-500">{body}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-alert/30 bg-alert-100 p-4 text-alert">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="flex-1"><p className="font-medium">{error.message}</p></div>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw className="h-4 w-4" aria-hidden="true" />Try again</Button>}
    </div>
  );
}
export const Notice = ({ tone = "signal", children }: { tone?: "signal" | "alert" | "petrol" | "ok"; children: ReactNode }) => {
  const t = { signal: "bg-signal-100 text-[#5C3F00] border-signal/40", alert: "bg-alert-100 text-alert border-alert/30", petrol: "bg-petrol-50 text-petrol-700 border-petrol-200", ok: "bg-ok-100 text-ok border-ok/30" };
  return <div role="status" className={cn("rounded-xl border px-4 py-3 text-sm", t[tone])}>{children}</div>;
};

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-3xl font-semibold sm:text-4xl">{title}</h1>{subtitle && <p className="mt-1 max-w-2xl text-ink-500">{subtitle}</p>}</div>
      {actions}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-xl bg-mist-200 p-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cn("h-9 rounded-lg px-4 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol-600", value === t.id ? "bg-white text-ink shadow-sm" : "text-ink-500 hover:text-ink")}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Disclosure({ summary, children, defaultOpen }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="group rounded-xl border border-mist-200 bg-mist-50">
      <summary className="flex min-h-11 items-center justify-between gap-2 px-4 py-2 text-sm font-medium text-ink-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol-600">
        {summary}<span className="text-ink-400 transition group-open:rotate-90" aria-hidden="true">›</span>
      </summary>
      <div className="px-4 pb-4 text-sm text-ink-700">{children}</div>
    </details>
  );
}

export const inputCls = "h-11 w-full rounded-xl border border-mist-300 bg-white px-3 text-[15px] text-ink placeholder:text-ink-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-petrol-600";
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1 block text-sm font-medium text-ink-700">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-ink-500">{hint}</span>}</label>;
}
