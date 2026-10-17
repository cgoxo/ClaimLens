import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { proposal } from "../test/chat";
import ProposalCard from "./ProposalCard";

const setup = (p = proposal(), onDecide = vi.fn(async () => {}), title = "Edited total") => {
  render(<ProposalCard proposal={p} findingTitle={title} onDecide={onDecide} />);
  return onDecide;
};

test("states the change in plain words, with the reason", () => {
  setup();
  expect(screen.getByText("Dismiss: Edited total")).toBeInTheDocument();
  expect(screen.getByText("It is a scanner artefact.")).toBeInTheDocument();
});

test.each([
  [{ type: "set_severity" as const, severity: "medium" as const }, "Change severity to medium: Edited total"],
  [{ type: "add_finding" as const, title: "Late admission" }, "Add finding: Late admission"],
  [{ type: "correct_fact" as const, path: "claim.amount_claimed", value: 18450 }, "Correct claim.amount_claimed to 18450"],
])("describes %o", (over, text) => {
  setup(proposal(over));
  expect(screen.getByText(text)).toBeInTheDocument();
});

test("Apply and Ignore call onDecide", async () => {
  const onDecide = setup();
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onDecide).toHaveBeenCalledWith("apply");
  await userEvent.click(screen.getByRole("button", { name: "Ignore" }));
  expect(onDecide).toHaveBeenCalledWith("ignore");
});

test.each([
  ["applied", "Applied"], ["ignored", "Ignored"], ["applying", "Applying…"],
  ["stale", "Changed since — ask again"],
] as const)("%s shows %s and no buttons", (status, text) => {
  setup(proposal({ status }));
  expect(screen.getByText(text)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
});

test("failed shows the error", () => {
  setup(proposal({ status: "failed", error: "Could not recalculate" }));
  expect(screen.getByText("Failed: Could not recalculate")).toBeInTheDocument();
});

test("a refused decision shows why", async () => {
  setup(proposal(), vi.fn(async () => { throw new Error("Already decided"); }));
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(await screen.findByText("Already decided")).toBeInTheDocument();
});
