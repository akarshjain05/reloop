import { useEffect, useState } from "react";
import { ArrowRight, Sparkles, Trophy } from "lucide-react";
import { kg, num } from "../lib/format";
import { Card, Notice } from "./ui";

export function useCountUp(target: number, ms = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || target === 0) { setV(target); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (t: number) => { const p = Math.min(1, (t - t0) / ms); setV(Math.round(target * (1 - Math.pow(1 - p, 3)))); if (p < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

/** The reward moment: points, material diverted, estimated CO2e, and what it changed for the person and their building. */
export function Reward({ rewards }: { rewards: any }) {
  const pts = useCountUp(rewards.points);
  const up = rewards.rank_before && rewards.rank_after && rewards.rank_after < rewards.rank_before;
  const scoreUp = rewards.building_score_before != null && rewards.building_score_after != null;
  return (
    <Card tone="petrol" className="rounded-hero animate-pop" aria-label="Rewards">
      <div className="flex items-center gap-2 text-petrol-100"><Sparkles className="h-5 w-5" aria-hidden="true" /><span className="font-medium">Verified. Here is what it changed</span></div>
      <div className="mt-4 grid gap-5 sm:grid-cols-3">
        <div><div className="font-display text-5xl font-semibold tabular-nums text-signal" aria-label={`${rewards.points} points`}>+{pts}</div><div className="text-petrol-100">ReLoop points{rewards.points_held ? " (held for review)" : ""}</div></div>
        <div><div className="font-display text-3xl font-semibold tabular-nums">+{kg(rewards.kg)}</div><div className="text-petrol-100">diverted from landfill</div></div>
        <div><div className="font-display text-3xl font-semibold tabular-nums">~{num(rewards.co2e_kg, 1)} kg</div><div className="text-petrol-100">CO₂e avoided (estimate)</div></div>
      </div>
      <ul className="mt-5 space-y-2 text-[15px]">
        {up && <li className="flex items-center gap-2"><Trophy className="h-4 w-4 text-signal" aria-hidden="true" />You moved up {rewards.rank_before - rewards.rank_after} places: #{rewards.rank_before} <ArrowRight className="h-4 w-4" aria-hidden="true" /> #{rewards.rank_after} this month.</li>}
        {rewards.tier_after && rewards.tier_after !== rewards.tier_before && <li className="flex items-center gap-2"><Trophy className="h-4 w-4 text-signal" aria-hidden="true" />New tier reached: {rewards.tier_after}.</li>}
        {rewards.tier_after === rewards.tier_before && rewards.next_tier && <li>{rewards.points_to_next_tier} more points to reach {rewards.next_tier}.</li>}
        {scoreUp && <li>Your building's ReLoop Score: {rewards.building_score_before} <ArrowRight className="inline h-4 w-4" aria-hidden="true" /> {rewards.building_score_after}</li>}
        {rewards.challenge_events?.map((e: any, i: number) => <li key={i}>{e.challenge} reached {e.milestone}%.</li>)}
      </ul>
      {rewards.awards?.[0]?.breakdown && (
        <details className="mt-4 rounded-xl bg-white/10 p-3 text-sm">
          <summary className="cursor-pointer font-medium">How these points were calculated</summary>
          <ul className="mt-2 space-y-1">{rewards.awards[0].breakdown.map((b: any, i: number) => <li key={i} className="flex justify-between gap-3"><span>{b.label}{b.detail ? ` (${b.detail})` : ""}</span><span className="tabular-nums">{b.points}</span></li>)}</ul>
          {rewards.awards[0].capped && <p className="mt-2 text-signal">Daily points cap reached, so the rest was not awarded.</p>}
        </details>
      )}
      {rewards.points_held && <div className="mt-4"><Notice tone="signal">Some points are pending review while we double-check a flagged submission.</Notice></div>}
    </Card>
  );
}
