import { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { AuthContext, User } from "../lib/auth";
import { RuntimeContext } from "../lib/runtime";
import { FX } from "./mockApi";

export function Providers({ children, route = "/", user, persona = "demo" }: { children: ReactNode; route?: string; user?: User; persona?: "demo" | "org" | "admin" }) {
  const status = FX[persona]["/system/status"];
  return (
    <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <RuntimeContext.Provider value={{ status, offline: false, proof: null, setProof: vi.fn(), open: false, setOpen: vi.fn() }}>
        <AuthContext.Provider value={{ user: user ?? null, loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>{children}</AuthContext.Provider>
      </RuntimeContext.Provider>
    </MemoryRouter>
  );
}
export const photo = (name = "laptop.jpg") => new File([new Uint8Array([255, 216, 255, 224])], name, { type: "image/jpeg" });
