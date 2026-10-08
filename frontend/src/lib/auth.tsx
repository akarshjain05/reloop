import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, getToken, setToken } from "./api";

export interface User { id: string; email: string; name: string; role: "USER" | "COLLECTOR" | "ADMIN" | "ORGANIZATION_ADMIN"; org_id?: string; building_id?: string }
interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (b: { email: string; password: string; name: string; building_id?: string }) => Promise<User>;
  logout: () => void;
}
export const AuthContext = createContext<AuthValue>({ user: null, loading: false, login: async () => { throw new Error("no provider"); }, register: async () => { throw new Error("no provider"); }, logout: () => {} });
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  const logout = useCallback(() => { setToken(null); setUser(null); }, []);
  useEffect(() => {
    if (!getToken()) return;
    api.get<User>("/auth/me").then(setUser, () => setToken(null)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    const h = () => setUser(null);
    window.addEventListener("reloop:signout", h);
    return () => window.removeEventListener("reloop:signout", h);
  }, []);
  const value = useMemo<AuthValue>(() => ({
    user, loading, logout,
    login: async (email, password) => { const r = await api.post("/auth/login", { email, password }); setToken(r.access_token); setUser(r.user); return r.user; },
    register: async (b) => { const r = await api.post("/auth/register", b); setToken(r.access_token); setUser(r.user); return r.user; },
  }), [user, loading, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="grid min-h-screen place-items-center text-ink-500" role="status">Loading…</div>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
export const homeFor = (u: User) => (u.role === "ADMIN" || u.role === "COLLECTOR" ? "/ops" : "/dashboard");
