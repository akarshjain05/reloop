import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import Advisor from "../pages/Advisor";
import Challenges from "../pages/Challenges";
import Dashboard from "../pages/Dashboard";
import Exchange from "../pages/Exchange";
import Impact from "../pages/Impact";
import Landing from "../pages/Landing";
import Leaderboard from "../pages/Leaderboard";
import Login from "../pages/Login";
import Ops from "../pages/Ops";
import Organization from "../pages/Organization";
import Recyclers from "../pages/Recyclers";
import Scan from "../pages/Scan";
import { Providers } from "./helpers";
import { FX, mock, reset } from "./mockApi";

vi.mock("../lib/api", async (orig) => (await import("./mockApi")).apiFactory(orig as any));
const demo = FX.flows.demo_user;

// Every screen renders against REAL payloads captured from the backend (scripts/capture_fixtures.py).
describe("every page renders with real API payloads", () => {
  beforeEach(() => reset("demo"));
  const pages: [string, JSX.Element, RegExp][] = [
    ["Dashboard", <Dashboard />, /Welcome back, Akarsh/],
    ["Scan", <Scan />, /WasteLens/],
    ["Exchange", <Exchange />, /ReLoop Exchange/],
    ["Recyclers", <Recyclers />, /Find a recycler/],
    ["Leaderboard", <Leaderboard />, /^Leaderboard$/],
    ["Challenges", <Challenges />, /^Challenges$/],
    ["Impact", <Impact />, /My impact/],
    ["Advisor", <Advisor />, /ReLoop Advisor/],
    ["Organization (resident)", <Organization />, /Hostel Block A/],
  ];
  it.each(pages)("%s", async (_n, el, heading) => {
    render(<Providers user={demo}>{el}</Providers>);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // no error state
  });

  it("Exchange labels everything as an estimate and filters by action", async () => {
    const user = userEvent.setup();
    render(<Providers user={demo}><Exchange /></Providers>);
    expect(await screen.findByText(/These are not live market prices/)).toBeInTheDocument();
    expect(screen.getByText("MacBook Air (M1, 2020)")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Recycle" }));
    expect(screen.queryByText("MacBook Air (M1, 2020)")).not.toBeInTheDocument();
    expect(screen.getByText("Laptop with cracked screen")).toBeInTheDocument();
  });

  it("Recyclers shows the demo-data notice, distances, and never claims real authorisation", async () => {
    render(<Providers user={demo}><Recyclers /></Providers>);
    expect(await screen.findByText(/fictional demo entries/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/km/)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/officially authori[sz]ed recycler/i)).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Directions/ })[0]).toHaveAttribute("target", "_blank");
  });

  it("Leaderboard uses positive messaging and switches scope", async () => {
    const user = userEvent.setup();
    mock.fx["/leaderboard/neighborhood?period=month"] = FX.demo["/leaderboard/neighborhood?period=month"];
    render(<Providers user={demo}><Leaderboard /></Providers>);
    expect(await screen.findByText(/more points to reach/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Neighborhood" }));
    expect(await screen.findByRole("heading", { name: /Top buildings in/ })).toBeInTheDocument();
  });

  it("Advisor separates verified data from the AI-generated recommendation", async () => {
    const user = userEvent.setup();
    mock.handlers["POST /advisor/chat"] = () => FX.flows.advisor;
    render(<Providers user={demo}><Advisor /></Providers>);
    await user.click(screen.getByRole("button", { name: "How can my building improve?" }));
    expect(await screen.findByText("Verified data")).toBeInTheDocument();
    expect(screen.getByText("AI-generated recommendation")).toBeInTheDocument();
    expect(screen.getAllByText(/Building statistics|Configured impact assumptions/).length).toBeGreaterThan(0);
  });

  it("Organization explains how the ReLoop Score was calculated", async () => {
    render(<Providers user={demo}><Organization /></Providers>);
    expect(await screen.findByText("How it was calculated")).toBeInTheDocument();
    expect(screen.getByText(/ReLoop Score = 30 x participation/)).toBeInTheDocument();
    expect(screen.getByText(/Next best action for Hostel Block A/)).toBeInTheDocument();
  });
});

describe("staff screens", () => {
  it("campus admin sees the whole campus with building ranking", async () => {
    reset("org");
    render(<Providers persona="org" user={FX.flows.org_user}><Organization /></Providers>);
    expect(await screen.findByRole("heading", { level: 1, name: /SVNIT Green Campus/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buildings" })).toBeInTheDocument();
    expect(screen.getByText("Create this campaign")).toBeInTheDocument();
  });

  it("admin operations: queue, fraud review, AI review, analytics, people, recyclers", async () => {
    reset("admin");
    const user = userEvent.setup();
    render(<Providers persona="admin" user={FX.flows.admin_user}><Ops /></Providers>);
    expect(await screen.findByRole("heading", { level: 1, name: "Operations" })).toBeInTheDocument();
    expect(await screen.findAllByRole("button", { name: /Mark scheduled|Assign collector|Mark picked up|Verify and award points/ })).not.toHaveLength(0);
    await user.click(screen.getByRole("tab", { name: "Fraud review" }));
    expect((await screen.findAllByText("Suspicious submission detected")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("tab", { name: "AI review" }));
    expect(await screen.findByRole("table", { name: "Recent AI classifications" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Analytics" }));
    expect(await screen.findByText("AI accuracy feedback")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "People and exports" }));
    expect(await screen.findByText("Export CSV")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Recyclers" }));
    expect(await screen.findByText("Add a recycler")).toBeInTheDocument();
    expect(screen.getAllByText("Demo data").length).toBeGreaterThan(0);
  });

  it("a collector only gets the pickup queue", async () => {
    reset("admin");
    mock.fx["/pickups"] = FX.flows.collector_pickups;
    render(<Providers persona="admin" user={FX.flows.collector_user}><Ops /></Providers>);
    expect(await screen.findByRole("heading", { level: 1, name: "Operations" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Fraud review" })).not.toBeInTheDocument();
  });
});

describe("shell, landing and sign-in", () => {
  it("landing page shows the headline, both CTAs and labels its numbers as demo data", async () => {
    reset("demo");
    render(<Providers><Landing /></Providers>);
    expect(screen.getByRole("heading", { level: 1, name: /Turn waste into value\./ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Scan Your E-Waste/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Explore Impact" })).toHaveAttribute("href", "#impact");
    expect(await screen.findByText("Demo numbers")).toBeInTheDocument();
  });

  it("login offers one-click demo accounts and a skip-friendly form", async () => {
    reset("demo");
    render(<Providers><Login /></Providers>);
    expect(await screen.findByText("Try a demo account")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resident (Akarsh)" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
  });

  it("the app shell has landmarks, a skip link, runtime badge and role-aware navigation", async () => {
    reset("demo");
    const { unmount } = render(<Providers route="/dashboard" user={demo}><App /></Providers>);
    expect(await screen.findByRole("heading", { level: 1, name: /Welcome back/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show runtime and AWS details/ })).toHaveTextContent("Demo mode");
    expect(screen.queryByRole("link", { name: "Operations" })).not.toBeInTheDocument();
    unmount();
    reset("admin");
    render(<Providers persona="admin" route="/dashboard" user={FX.flows.admin_user}><App /></Providers>);
    expect(await screen.findByRole("link", { name: "Operations" })).toBeInTheDocument();
  });
});
