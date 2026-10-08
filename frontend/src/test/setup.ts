import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());
class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver = (globalThis as any).ResizeObserver ?? RO;
window.matchMedia = window.matchMedia ?? ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false }) as any);
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});
URL.createObjectURL = URL.createObjectURL ?? (() => "blob:test");

// jsdom has no layout, so Recharts warns about 0x0 containers. That is expected here and not a product problem.
const noise = [/The width\(0\) and height\(0\) of chart/];
for (const level of ["warn", "error"] as const) {
  const orig = console[level].bind(console);
  console[level] = (...a: unknown[]) => { if (typeof a[0] === "string" && noise.some((r) => r.test(a[0] as string))) return; orig(...a); };
}
