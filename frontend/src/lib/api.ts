const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "").replace(/\/$/, "") || "/api";
const KEY = "reloop_token";

export class ApiError extends Error {
  status: number;
  code: string;
  fields?: { field: string; message: string }[];
  retryAfter?: number;
  constructor(status: number, code: string, message: string, extra: any = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = extra?.fields;
    this.retryAfter = extra?.retry_after;
  }
}

function readToken(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
let token: string | null = readToken();

export function setToken(t: string | null) {
  token = t;
  try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
}
export const getToken = () => token;

async function request<T = any>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "network", "Can't reach ReLoop right now. Check your connection and try again.");
  }
  if (res.status === 401 && token && !path.startsWith("/auth/")) {
    setToken(null);
    window.dispatchEvent(new Event("reloop:signout"));
  }
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* non-JSON body */ }
  if (!res.ok) {
    const e = data?.error;
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? "Something went wrong. Please try again.", e);
  }
  return data as T;
}

export const api = {
  get: <T = any>(p: string) => request<T>("GET", p),
  post: <T = any>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  patch: <T = any>(p: string, b?: unknown) => request<T>("PATCH", p, b ?? {}),
  upload: <T = any>(p: string, file: File, fields: Record<string, string> = {}) => {
    const f = new FormData();
    f.append("image", file, file.name);
    Object.entries(fields).forEach(([k, v]) => v && f.append(k, v));
    return request<T>("POST", p, undefined, f);
  },
  async download(path: string, filename: string) {
    const res = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) throw new ApiError(res.status, "download_failed", "Couldn't download that file.");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 150);
  },
  mediaUrl: (u?: string | null) => (!u ? "" : u.startsWith("/media/") ? `${BASE}${u}` : u),
};

/** Downscale phone photos before upload (keeps requests small and fast; the server also re-encodes and strips EXIF). */
export async function resizeImage(file: File, maxDim = 1280, quality = 0.85): Promise<File> {
  try {
    if (typeof createImageBitmap !== "function") return file;
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, maxDim / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob: Blob | null = await new Promise((r) => canvas.toBlob(r, "image/jpeg", quality));
    if (!blob) return file;
    return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}
