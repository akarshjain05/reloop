import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { setLocale } from "./format";

export interface Runtime {
  demo_mode: boolean; on_aws: boolean; banner: string;
  runtime: { ai: string; model_id: string; bedrock_region: string | null; agent: string; store: string; table: string | null; storage: string; bucket: string | null; auth: string; region: string; in_lambda: boolean };
  demo_accounts: { email: string; role: string; password: string }[];
  locale?: { symbol: string; locale: string; unit: string; currency: string };
}
interface Ctx { status: Runtime | null; offline: boolean; proof: any | null; setProof: (p: any) => void; open: boolean; setOpen: (o: boolean) => void }
export const RuntimeContext = createContext<Ctx>({ status: null, offline: false, proof: null, setProof: () => {}, open: false, setOpen: () => {} });
export const useRuntime = () => useContext(RuntimeContext);

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Runtime | null>(null);
  const [offline, setOffline] = useState(false);
  const [proof, setProof] = useState<any | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { api.get<Runtime>("/system/status").then((s) => { if (s.locale) setLocale({ symbol: s.locale.symbol, locale: s.locale.locale }); setStatus(s); }, () => setOffline(true)); }, []);
  return <RuntimeContext.Provider value={{ status, offline, proof, setProof, open, setOpen }}>{children}</RuntimeContext.Provider>;
}
