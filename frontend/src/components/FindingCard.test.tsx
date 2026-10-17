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

describe("history", () => {
  const rows = [
    { version: 1, action: "analysis", by: "pipeline", at: "2026-10-10T10:00:00Z", note: "", finding: dismissed },
    { version: 2, action: "dismiss", by: "a@x.com", at: "2026-10-11T10:00:00Z", note: "duplicate", finding: dismissed },
  ];
  const card = (loadVersions?: () => Promise<typeof rows>) =>
    render(<FindingCard finding={sampleCase.findings[0]} number={1} selected onSelect={vi.fn()} onReview={vi.fn()}
      loadVersions={loadVersions} />);

  test("the History link loads and lists versions", async () => {
    card(vi.fn(async () => rows));
    await userEvent.click(screen.getByRole("button", { name: "History" }));
    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("v1");
    expect(items[0]).toHaveTextContent("Found by the analysis");
    expect(items[1]).toHaveTextContent("Dismissed");
    expect(items[1]).toHaveTextContent("a@x.com");
    expect(items[1]).toHaveTextContent("duplicate");
  });

  test("a failed load says so and can be retried", async () => {
    card(vi.fn().mockRejectedValueOnce(new Error("x")).mockResolvedValue(rows));
    await userEvent.click(screen.getByRole("button", { name: "History" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load the history");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findAllByRole("listitem")).toHaveLength(2);
  });
});
