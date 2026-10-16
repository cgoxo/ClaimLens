import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Finding } from "../api/types";
import { sampleCase } from "../test/sampleCase";
import FindingCard from "./FindingCard";

const dismissed: Finding = {
  ...sampleCase.findings[0],
  review: { action: "dismiss", note: "", by: "a@x.com", at: "2026-10-10T10:00:00Z" },
};

test("a dismissed finding can be restored", async () => {
  const onReview = vi.fn(async () => ({ ...dismissed, review: null }));
  render(<FindingCard finding={dismissed} number={1} selected onSelect={vi.fn()} onReview={onReview} />);
  await userEvent.click(screen.getByRole("button", { name: "Restore" }));
  expect(onReview).toHaveBeenCalledWith("restore", "");
  expect(await screen.findByRole("button", { name: "Accept" })).toBeInTheDocument();
});

test("an accepted finding has no Restore button", () => {
  const accepted = { ...dismissed, review: { ...dismissed.review!, action: "accept" as const } };
  render(<FindingCard finding={accepted} number={1} selected onSelect={vi.fn()} onReview={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Restore" })).toBeNull();
});
