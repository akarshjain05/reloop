import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, Send, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, inputCls, Notice, PageHeader } from "../components/ui";
import { api, ApiError } from "../lib/api";

const QUICK = ["What should I do with this?", "How much is my e-waste worth?", "Where can I recycle this?", "How can my building improve?", "What should I recycle next?"];
interface Msg { role: "user" | "assistant"; content: string; data?: any }

function Answer({ d }: { d: any }) {
  return (
    <div className="space-y-3">
      {d.verified.length > 0 && (
        <div className="rounded-xl border border-mist-200 bg-white p-3">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-ok"><ShieldCheck className="h-4 w-4" aria-hidden="true" />Verified data</div>
          <dl className="mt-2 divide-y divide-mist-200 text-sm">{d.verified.map((f: any, i: number) => <div key={i} className="flex flex-wrap justify-between gap-x-4 py-1.5"><dt className="text-ink-700">{f.label}<span className="block text-xs text-ink-400">{f.source}</span></dt><dd className="text-right font-medium tabular-nums">{f.value}</dd></div>)}</dl>
        </div>
      )}
      <div className="rounded-xl border border-signal/50 bg-signal-100 p-3">
        <div className="flex flex-wrap items-center gap-2"><Badge tone="signal">{d.recommendation.label}</Badge><span className="text-xs text-[#5C3F00]">{d.recommendation.generated_by === "bedrock" ? "Written by Amazon Bedrock from the data above" : "Written by rules from the data above"}</span></div>
        <p className="mt-2 text-[15px] text-ink">{d.recommendation.text}</p>
      </div>
      {d.actions.length > 0 && <div className="flex flex-wrap gap-2">{d.actions.map((a: any) => <Link key={a.route + a.label} to={a.route} className="inline-flex h-10 items-center rounded-xl border border-petrol-200 bg-petrol-50 px-4 text-sm font-semibold text-petrol-700 hover:bg-petrol-100">{a.label}</Link>)}</div>}
      <p className="text-xs text-ink-500">{d.disclaimer}</p>
    </div>
  );
}

export default function Advisor() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [msgs, busy]);

  const ask = async (q: string) => {
    if (!q.trim() || busy) return;
    const history = msgs.slice(-6).map((m) => ({ role: m.role, content: m.role === "assistant" ? m.data.recommendation.text : m.content }));
    setMsgs((m) => [...m, { role: "user", content: q }]); setText(""); setBusy(true); setErr(null);
    try { const data = await api.post("/advisor/chat", { message: q, history }); setMsgs((m) => [...m, { role: "assistant", content: data.recommendation.text, data }]); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "The Advisor couldn't answer. Please try again."); } finally { setBusy(false); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); ask(text); };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="ReLoop Advisor" subtitle="Grounded in your own records, your building's numbers and the recycler directory. Verified facts are kept separate from the generated recommendation." />
      <div className="space-y-4" aria-live="polite">
        {msgs.length === 0 && (
          <Card tone="mist"><div className="flex items-center gap-2"><Bot className="h-5 w-5 text-petrol-600" aria-hidden="true" /><h2 className="text-lg font-semibold">Ask about what to do next</h2></div>
            <p className="mt-1 text-ink-700">Try a quick prompt, or type your own question like "I have 8 kg of e-waste. Should I schedule a pickup?"</p></Card>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="flex justify-end"><p className="max-w-[85%] rounded-2xl rounded-br-md bg-petrol-600 px-4 py-2.5 text-white">{m.content}</p></div>
        ) : <div key={i}><Answer d={m.data} /></div>)}
        {busy && <p className="text-ink-500" role="status">Looking at your data…</p>}
        {err && <Notice tone="alert">{err}</Notice>}
        <div ref={end} />
      </div>
      <div className="sticky bottom-24 mt-6 space-y-3 rounded-2xl bg-mist-100/95 pb-2 pt-3 backdrop-blur lg:bottom-0">
        <div className="flex flex-wrap gap-2">{QUICK.map((q) => <button key={q} onClick={() => ask(q)} disabled={busy} className="min-h-10 rounded-full border border-mist-300 bg-white px-3.5 text-sm font-medium hover:bg-mist-50 disabled:opacity-50">{q}</button>)}</div>
        <form onSubmit={submit} className="flex gap-2">
          <label className="grow"><span className="sr-only">Ask the Advisor</span><input className={inputCls} value={text} onChange={(e) => setText(e.target.value)} maxLength={500} placeholder="Ask about an item, a pickup, or your building" /></label>
          <Button type="submit" size="md" disabled={!text.trim() || busy} aria-label="Send"><Send className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">Ask</span></Button>
        </form>
      </div>
    </div>
  );
}
