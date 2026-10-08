import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Advisor from "../pages/Advisor";
import Challenges from "../pages/Challenges";
import Dashboard from "../pages/Dashboard";
import Exchange from "../pages/Exchange";
import Landing from "../pages/Landing";
import Leaderboard from "../pages/Leaderboard";
import Login from "../pages/Login";
import Organization from "../pages/Organization";
import Pickup from "../pages/Pickup";
import Recyclers from "../pages/Recyclers";
import Scan from "../pages/Scan";
import { Providers, photo } from "./helpers";
import { FX, mock, reset } from "./mockApi";

vi.mock("../lib/api", async (orig) => (await import("./mockApi")).apiFactory(orig as any));

// Structural accessibility audit (names, labels, roles, landmarks, headings, lists). Colour contrast needs a real
// browser: the palette was chosen for it, but it is NOT verified here (see README, "Known limitations").
async function violations(container: HTMLElement) {
  const r = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
  return r.violations.map((v) => `${v.id}: ${v.help} -> ${v.nodes.slice(0, 2).map((n) => n.html.slice(0, 120)).join(" | ")}`);
}
const wait = () => new Promise((r) => setTimeout(r, 60));

describe("axe structural audit", () => {
  beforeEach(() => reset("demo"));
  const pages: [string, JSX.Element][] = [
    ["Landing", <Landing />], ["Login", <Login />], ["Dashboard", <Dashboard />], ["Scan (idle)", <Scan />], ["Exchange", <Exchange />],
    ["Recyclers", <Recyclers />], ["Leaderboard", <Leaderboard />], ["Challenges", <Challenges />], ["Advisor", <Advisor />], ["Organization", <Organization />],
  ];
  it.each(pages)("%s has no structural violations", async (_n, el) => {
    const { container } = render(<Providers user={FX.flows.demo_user}>{el}</Providers>);
    await wait();
    expect(await violations(container)).toEqual([]);
  });

  it("Scan result card and correction form have no violations", async () => {
    mock.handlers["UPLOAD /waste/analyze"] = () => FX.flows.analyze;
    const user = userEvent.setup();
    const { container, findByText, getByRole, getByTestId } = render(<Providers user={FX.flows.demo_user}><Scan /></Providers>);
    await user.upload(getByTestId("photo-input"), photo());
    await findByText("Likely identified");
    await user.click(getByRole("button", { name: "Correct result" }));
    expect(await violations(container)).toEqual([]);
  });

  it("Pickup wizard has no violations", async () => {
    const { container, findByRole } = render(<Providers route={`/pickup?s=${FX.flows.analyze.submission.id}`} user={FX.flows.demo_user}><Pickup /></Providers>);
    await findByRole("heading", { name: "Which items?" });
    expect(await violations(container)).toEqual([]);
  });
});
