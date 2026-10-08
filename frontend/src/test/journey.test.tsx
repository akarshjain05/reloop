import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import Pickup from "../pages/Pickup";
import { Providers } from "./helpers";
import { FX, mock, reset } from "./mockApi";

vi.mock("../lib/api", async (orig) => (await import("./mockApi")).apiFactory(orig as any));

beforeEach(() => {
  reset("demo");
  mock.handlers["POST /pickups"] = () => FX.flows.pickup_created;
  mock.handlers[`POST /pickups/${FX.flows.pickup_created.id}/fast-forward`] = () => FX.flows.pickup_verified;
});

it("schedule a pickup (items, address, time, confirm) and see the verified reward", async () => {
  const user = userEvent.setup();
  render(<Providers route={`/pickup?s=${FX.flows.analyze.submission.id}`} user={FX.flows.demo_user}><Pickup /></Providers>);

  expect(await screen.findByRole("heading", { name: "Which items?" })).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: /Laptop/ })).toBeChecked();
  await user.click(screen.getByRole("button", { name: "Continue" }));

  await user.type(await screen.findByLabelText("Address"), "Room 214, Hostel Block A, SVNIT");
  await user.click(screen.getByRole("button", { name: "Continue" }));

  const day = within(await screen.findByRole("radiogroup", { name: "Date" })).getAllByRole("radio")[0];
  await user.click(day);
  await user.click(within(screen.getByRole("radiogroup", { name: "Time slot" })).getByRole("radio", { name: "11:00-13:00" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));

  expect(await screen.findByRole("heading", { name: "Check and confirm" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Confirm request" }));
  expect(await screen.findByRole("heading", { name: "Pickup requested" })).toBeInTheDocument();
  const body = mock.calls.find((c) => c.method === "POST" && c.path === "/pickups")!.body;
  expect(body).toMatchObject({ mode: "pickup", slot: "11:00-13:00", submission_ids: [FX.flows.analyze.submission.id], address: { city: "Surat" } });

  await user.click(screen.getByRole("button", { name: "Simulate collection and verification" }));
  expect(await screen.findByLabelText(`${FX.flows.rewards.points} points`)).toBeInTheDocument();
  expect(screen.getByText(/Verified\. Here is what it changed/)).toBeInTheDocument();
});

it("explains the empty state when nothing is confirmed yet", async () => {
  mock.fx["/waste/history"] = [];
  render(<Providers user={FX.flows.demo_user}><Pickup /></Providers>);
  expect(await screen.findByText("No confirmed items yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Scan an item" })).toHaveAttribute("href", "/scan");
});
