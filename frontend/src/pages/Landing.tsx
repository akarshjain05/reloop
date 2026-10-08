import { ArrowRight, BadgeCheck, Gauge, MapPin, Recycle, ScanLine, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";
import { Badge, btn, Card, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { inrRange, num } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const LOOP = ["Discover", "Scan", "Understand", "Value", "Choose", "Act", "Verify", "Reward", "Measure", "Community improves"];

function ScanArt() {
  return (
    <svg viewBox="0 0 320 210" role="img" aria-label="Illustration of a laptop inside a scan frame" className="w-full">
      <rect x="62" y="34" width="196" height="124" rx="12" fill="#0A3F43" />
      <rect x="74" y="46" width="172" height="100" rx="6" fill="#14797F" />
      <path d="M96 118l24-30 20 22 16-14 28 28z" fill="#A3CFD1" opacity=".55" />
      <circle cx="208" cy="76" r="9" fill="#F5B83D" />
      <path d="M30 166h260l-20 22H50z" fill="#2A3C40" />
      <path d="M16 54V24a8 8 0 0 1 8-8h30M304 54V24a8 8 0 0 0-8-8h-30M16 156v30a8 8 0 0 0 8 8h30M304 156v30a8 8 0 0 1-8 8h-30" fill="none" stroke="#F5B83D" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export default function Landing() {
  const { user } = useAuth();
  const stats = useAsync(() => api.get("/public/stats"), []);
  const s = stats.data;
  return (
    <div className="bg-mist-100">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo />
        <nav aria-label="Site" className="flex items-center gap-2">
          <a href="#how" className="hidden h-10 items-center rounded-lg px-3 text-[15px] font-medium text-ink-700 hover:bg-mist-200 sm:inline-flex">How it works</a>
          <Link to={user ? "/dashboard" : "/login"} className={btn("outline", "md")}>{user ? "Open app" : "Sign in"}</Link>
        </nav>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-10 px-5 pb-16 pt-6 lg:grid-cols-[1.1fr_.9fr] lg:pt-12">
        <div>
          <h1 className="text-5xl font-bold leading-[1.02] sm:text-7xl">Turn waste <span className="text-petrol-600">into value.</span></h1>
          <p className="mt-5 max-w-xl text-lg text-ink-700 sm:text-xl">Identify your e-waste, find its next best destination, earn rewards, and see the environmental impact of every responsible action.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/scan" className={btn("signal", "lg")}><ScanLine className="h-5 w-5" aria-hidden="true" />Scan Your E-Waste</Link>
            <a href="#impact" className={btn("outline", "lg")}>Explore Impact</a>
          </div>
          <p className="mt-4 text-sm text-ink-500">Try it without signing up for anything: demo accounts are one click away.</p>
        </div>
        <Card className="rounded-hero p-5 shadow-sm" aria-label="Example scan result">
          <div className="rounded-2xl bg-petrol-50 p-3"><ScanArt /></div>
          <div className="mt-4 flex flex-wrap items-center gap-2"><Badge tone="petrol">Likely identified</Badge><Badge tone="signal">AI estimate</Badge></div>
          <div className="mt-1 flex items-baseline justify-between"><h2 className="text-3xl font-semibold">Laptop</h2><span className="tabular-nums text-ink-500">91% confidence</span></div>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl bg-mist-50 p-3"><dt className="text-ink-500">Estimated resale</dt><dd className="font-display text-lg font-semibold">{inrRange({ min: 6000, max: 22000 })}</dd></div>
            <div className="rounded-xl bg-mist-50 p-3"><dt className="text-ink-500">Potential impact</dt><dd className="font-display text-lg font-semibold">~6.4 kg CO₂e</dd></div>
          </dl>
          <p className="mt-3 rounded-xl bg-petrol-50 p-3 font-display text-lg font-semibold text-petrol-700">Resell if it works, recycle if it doesn't</p>
          <p className="mt-2 text-xs text-ink-500">Example result using demo data. Estimates only; you confirm the item before anything happens.</p>
        </Card>
      </section>

      <section id="how" className="border-y border-mist-200 bg-white py-14">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-3xl font-semibold sm:text-4xl">One loop, from the drawer to measurable impact</h2>
          <ol className="mt-6 flex flex-wrap gap-2">{LOOP.map((l, i) => <li key={l} className="flex items-center gap-2 rounded-full bg-mist-100 py-1.5 pl-1.5 pr-4 text-[15px] font-medium"><span className="grid h-7 w-7 place-items-center rounded-full bg-petrol-600 text-xs font-bold text-white tabular-nums">{i + 1}</span>{l}</li>)}</ol>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {[
              { i: Gauge, t: "Know what it's worth", b: "A photo gives you an estimated resale and recycling range, and a plain recommendation: resell, repair, recycle or donate." },
              { i: MapPin, t: "Know where to take it", b: "See nearby drop-offs with distance, accepted items and pickup options, or book a pickup from your door." },
              { i: BadgeCheck, t: "See what it did", b: "Points land only after a verified pickup. Your building's score and CO₂e estimate move, and your Advisor tells you what to do next." },
            ].map((c) => <Card key={c.t} tone="mist"><c.i className="h-7 w-7 text-petrol-600" aria-hidden="true" /><h3 className="mt-3 text-xl font-semibold">{c.t}</h3><p className="mt-1 text-ink-700">{c.b}</p></Card>)}
          </div>
        </div>
      </section>

      <section id="impact" className="mx-auto max-w-6xl px-5 py-14">
        <div className="flex flex-wrap items-center gap-3"><h2 className="text-3xl font-semibold sm:text-4xl">Community impact so far</h2><Badge tone="signal">Demo numbers</Badge></div>
        <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[["Items diverted", s && num(s.items)], ["Kilograms recycled", s && num(s.kg)], ["Active users", s && num(s.active_users)], ["CO₂e avoided (estimate)", s && `${num(s.co2e_kg)} kg`]].map(([l, v]) => (
            <Card key={String(l)}><div className="text-sm text-ink-500">{l}</div>{v ? <div className="font-display text-4xl font-semibold tabular-nums">{v}</div> : <Skeleton className="mt-1 h-10 w-24" />}</Card>
          ))}
        </div>
        <p className="mt-3 text-sm text-ink-500">{s?.note ?? "Seeded demo data plus live activity."} Figures are labeled estimates, not audited results.</p>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-16">
        <Card tone="petrol" className="rounded-hero p-8">
          <h2 className="flex items-center gap-2 text-2xl font-semibold"><ShieldCheck className="h-6 w-6 text-signal" aria-hidden="true" />How we keep it honest</h2>
          <ul className="mt-4 grid gap-3 text-petrol-100 sm:grid-cols-2">
            <li>AI results are estimates with a confidence score, and you can always correct them.</li>
            <li>Prices come from a curated dataset and are labeled as estimated ranges, never live offers.</li>
            <li>Points are awarded after a verified pickup or drop-off, with duplicate-photo checks and daily caps.</li>
            <li>Impact figures use configured assumptions you can read, change and cite.</li>
          </ul>
          <Link to="/login" className={btn("signal", "lg", "mt-6")}>Try the demo<ArrowRight className="h-5 w-5" aria-hidden="true" /></Link>
        </Card>
      </section>

      <footer className="border-t border-mist-200 bg-white py-8 text-sm text-ink-500">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5">
          <span className="flex items-center gap-2"><Recycle className="h-4 w-4 text-petrol-600" aria-hidden="true" />ReLoop, built for the Waste and Energy track.</span>
          <span>Runs on Amazon Bedrock, Strands Agents, Lambda, API Gateway, DynamoDB, S3, Cognito and CloudFront.</span>
        </div>
      </footer>
    </div>
  );
}
