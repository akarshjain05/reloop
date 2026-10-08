import { vi } from "vitest";
import fixtures from "./fixtures.json";

/** Real responses captured from the seeded backend by scripts/capture_fixtures.py. */
export const FX: any = fixtures;
export const mock = {
  fx: {} as Record<string, any>,
  handlers: {} as Record<string, (body: any) => any>,
  calls: [] as { method: string; path: string; body?: any }[],
};

export async function apiFactory(orig: () => Promise<any>) {
  const actual = await orig();
  const respond = (method: string, path: string, body?: any) => {
    mock.calls.push({ method, path, body });
    const h = mock.handlers[`${method} ${path}`];
    if (h) return Promise.resolve(h(body));
    if (method === "GET" && path in mock.fx) return Promise.resolve(mock.fx[path]);
    return Promise.reject(new actual.ApiError(404, "no_fixture", `No fixture for ${method} ${path}`));
  };
  return {
    ...actual,
    api: {
      get: (p: string) => respond("GET", p),
      post: (p: string, b?: any) => respond("POST", p, b ?? {}),
      patch: (p: string, b?: any) => respond("PATCH", p, b ?? {}),
      upload: (p: string, f: File, fields?: any) => respond("UPLOAD", p, { name: f.name, fields }),
      download: vi.fn(),
      mediaUrl: actual.api.mediaUrl,
    },
  };
}

export function reset(persona: "demo" | "org" | "admin" = "demo") {
  mock.fx = { ...FX[persona] };
  mock.handlers = {};
  mock.calls = [];
}
