import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Reward } from "../components/Reward";
import Dashboard from "../pages/Dashboard";
import Scan from "../pages/Scan";
import { Providers, photo } from "./helpers";
import { FX, mock, reset } from "./mockApi";

vi.mock("../lib/api", async (orig) => (await import("./mockApi")).apiFactory(orig as any));

const sid = FX.flows.analyze.submission.id;
beforeEach(() => {
  reset("demo");
  mock.handlers["UPLOAD /waste/analyze"] = () => FX.flows.analyze;
  mock.handlers["POST /waste/confirm"] = (b) => (b.corrections ? FX.flows.confirm_damaged : FX.flows.confirm_plain);
  mock.handlers[`POST /waste/${sid}/action`] = () => ({ ...FX.flows.confirm_plain, action_hint: "Find a recycler or schedule a pickup to earn points once it's verified." });
});

async function scanLaptop() {
  const user = userEvent.setup();
  render(<Providers user={FX.flows.demo_user}><Scan /></Providers>);
  await user.upload(await screen.findByTestId("photo-input"), photo());
  await screen.findByText("Likely identified");
  return user;
}

describe("scan flow", () => {
  it("shows an honest AI result (confidence, estimates, labels) and lets the person confirm", async () => {
    const user = await scanLaptop();
    expect(screen.getByRole("heading", { name: "Laptop" })).toBeInTheDocument();
    expect(screen.getByText(/Confidence/)).toBeInTheDocument();
    expect(screen.getByText(/AI estimate — confirm item and condition for a more accurate value\./)).toBeInTheDocument();
    expect(screen.getByText(/Estimated range, not a guaranteed offer/)).toBeInTheDocument();
    expect(screen.getByText(/~6\.4 kg CO₂e avoided/)).toBeInTheDocument();
    for (const name of ["Confirm", "Correct result", "Find recycler", "Schedule pickup"]) expect(screen.getByRole("button", { name })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText(/Confirmed\. What would you like to do with it\?/)).toBeInTheDocument();
    expect(mock.calls.find((c) => c.path === "/waste/confirm")?.body).toEqual({ submission_id: sid, corrections: undefined });
    await user.click(screen.getByRole("button", { name: "Recycle" }));
    expect(await screen.findByText(/earn points once it's verified/)).toBeInTheDocument();
  });

  it("a correction re-estimates: damaged laptop -> recycle with a recycling value", async () => {
    const user = await scanLaptop();
    await user.click(screen.getByRole("button", { name: "Correct result" }));
    const form = await screen.findByRole("region", { name: "Correct the result" });
    await user.selectOptions(within(form).getByLabelText("Condition"), "damaged");
    await user.click(within(form).getByRole("button", { name: "Update estimate" }));
    expect(await screen.findByText("Updated with your corrections")).toBeInTheDocument();
    expect(screen.getByText("₹1,000 – ₹2,000")).toBeInTheDocument();
    expect(screen.getByText("Recycle through an authorised recycler")).toBeInTheDocument();
    expect(mock.calls.filter((c) => c.path === "/waste/confirm").pop()?.body.corrections).toMatchObject({ item_type: "laptop", condition: "damaged" });
  });

  it("flags a suspicious duplicate instead of hiding it", async () => {
    const flagged = { ...FX.flows.analyze, submission: { ...FX.flows.analyze.submission, fraud: { score: 70, status: "pending_review", flags: [{ code: "DUPLICATE_EXACT", detail: "This exact image was already submitted by you." }] } } };
    mock.handlers["UPLOAD /waste/analyze"] = () => flagged;
    await scanLaptop();
    expect(screen.getByText(/Suspicious submission detected\./)).toBeInTheDocument();
    expect(screen.getByText(/pending verification/)).toBeInTheDocument();
  });

  it("explains AI outages and opens manual correction", async () => {
    mock.handlers["UPLOAD /waste/analyze"] = () => ({ ...FX.flows.analyze, ai_status: "unavailable", message: "AI analysis is temporarily unavailable. You can select the item manually." });
    await scanLaptop();
    expect(screen.getByText(/You can select the item manually/)).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Correct the result" })).toBeInTheDocument();
  });

  it("shows a friendly message when no electronic item is found", async () => {
    mock.handlers["UPLOAD /waste/analyze"] = () => ({ ai_status: "no_item", message: "We couldn't spot an electronic item in that photo.", submission: null });
    const user = userEvent.setup();
    render(<Providers user={FX.flows.demo_user}><Scan /></Providers>);
    await user.upload(await screen.findByTestId("photo-input"), photo());
    expect(await screen.findByText(/couldn't spot an electronic item/)).toBeInTheDocument();
  });

  it("Scan My Waste: flags e-waste, the person removes it, the building score moves", async () => {
    mock.handlers["UPLOAD /waste/bin-scan"] = () => FX.flows.bin_scan;
    mock.handlers[`POST /waste/bin-scan/${FX.flows.bin_scan.id}/confirm`] = () => FX.flows.bin_confirm;
    const user = userEvent.setup();
    render(<Providers user={FX.flows.demo_user}><Scan /></Providers>);
    await user.click(screen.getByRole("tab", { name: "Scan my waste" }));
    await user.upload(await screen.findByTestId("photo-input"), photo("mixed-bin.jpg"));
    expect(await screen.findByText(/Remove the battery and electronic components/)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/taken out the e-waste items/i));
    await user.click(screen.getByRole("button", { name: /Confirm and update my building/ }));
    expect(await screen.findByText(/Thanks, that helps your building/)).toBeInTheDocument();
    expect(mock.calls.find((c) => c.path.endsWith("/confirm"))?.body.removed).toEqual(["e_waste"]);
  });
});

describe("points update", () => {
  it("the reward moment shows points, tier, rank and building score changes with estimate labels", () => {
    const r = FX.flows.rewards;
    render(<Providers user={FX.flows.demo_user}><Reward rewards={r} /></Providers>);
    expect(screen.getByLabelText(`${r.points} points`)).toBeInTheDocument();
    expect(screen.getByText(/New tier reached: Steward/)).toBeInTheDocument();
    expect(screen.getByText(/You moved up \d+ places/)).toBeInTheDocument();
    expect(screen.getByText(/Your building's ReLoop Score/)).toBeInTheDocument();
    expect(screen.getByText(/CO₂e avoided \(illustrative estimate\)/)).toBeInTheDocument();
    expect(screen.getByText("How these points were calculated")).toBeInTheDocument();
  });

  it("the dashboard reflects the ledger after verification", async () => {
    const { dashboard_before: before, dashboard_after: after, rewards } = FX.flows;
    expect(after.points.total - before.points.total).toBe(rewards.points);
    mock.fx["/dashboard"] = after;
    render(<Providers user={FX.flows.demo_user}><Dashboard /></Providers>);
    expect(await screen.findByText(new Intl.NumberFormat("en-IN").format(after.points.total))).toBeInTheDocument();
    expect(screen.getByText("Steward")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Welcome back, Akarsh/ })).toBeInTheDocument();
    expect(screen.getByText("Your next best action")).toBeInTheDocument();
  });
});
