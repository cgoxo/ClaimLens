import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CaseContextData } from "../api/types";
import { sampleCase } from "../test/sampleCase";
import CaseContext from "./CaseContext";

const context = sampleCase.context!;
const claim = context.claim as Record<string, { bbox: unknown }>;

function setup(ctx: CaseContextData = context, mismatch = false) {
  const onOpen = vi.fn();
  render(<CaseContext context={ctx} mismatch={mismatch} onOpen={onOpen} />);
  return onOpen;
}

test("shows the claim and the policy at a glance", () => {
  setup();
  expect(screen.getByRole("heading", { name: "The claim" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "The policy" })).toBeInTheDocument();
  expect(screen.getByText("Sunrise Eye & General Hospital, Pune")).toBeInTheDocument();
  expect(screen.getByText("Example Health Insurance Co.")).toBeInTheDocument();
  expect(screen.getAllByText("EH-2025-778812")).toHaveLength(2);
  expect(screen.getByText("Cataract · 24 months · clause 3.2")).toBeInTheDocument();
  const age = screen.getByText("Policy age at treatment").closest("div")!;
  expect(within(age).getByText("2 months")).toBeInTheDocument();
});

test("a missing value says so", () => {
  const { diagnosis: _, ...rest } = context.claim!;
  setup({ ...context, claim: rest });
  const row = screen.getByText("Diagnosis").closest("div")!;
  expect(within(row).getByText("Not found in documents")).toBeInTheDocument();
});

test("a page link opens the fact on its page", async () => {
  const onOpen = setup();
  await userEvent.click(screen.getByRole("button", { name: "Hospital, claim page 1" }));
  expect(onOpen).toHaveBeenCalledWith({
    doc: "claim", page: 1, quote: "Sunrise Eye & General Hospital, Pune", bbox: claim.hospital_name.bbox, source: "page",
  });
});

test("policy numbers are marked when they disagree", () => {
  setup(context, true);
  for (const value of screen.getAllByText("EH-2025-778812")) expect(value.closest("div")).toHaveClass("is-warning");
});
