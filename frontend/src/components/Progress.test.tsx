import { act, render, screen } from "@testing-library/react";
import type { CaseProgress } from "../api/types";
import Progress from "./Progress";

const reading: CaseProgress = { step: "READING", done: 3, total: 7, label: "Reading claim page 3 (3 of 7)" };

afterEach(() => vi.useRealTimers());

test("shows the label and a determinate bar", () => {
  render(<Progress status="READING" progress={reading} />);
  expect(screen.getByText("Reading claim page 3 (3 of 7)")).toBeInTheDocument();
  const bar = screen.getByRole("progressbar");
  expect(bar).toHaveAttribute("aria-valuenow", "3");
  expect(bar).toHaveAttribute("aria-valuemax", "7");
});

test("bar is indeterminate when there is no count", () => {
  render(<Progress status="CHECKING" progress={{ step: "CHECKING", done: 0, total: 0, label: "Extracting facts with Gemini" }} />);
  expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
});

test("says it is still working after 60 s without change, and hides it on change", () => {
  vi.useFakeTimers();
  const { rerender } = render(<Progress status="READING" progress={reading} />);
  expect(screen.queryByText("Still working. Large scans take longer.")).toBeNull();
  act(() => { vi.advanceTimersByTime(60_000); });
  expect(screen.getByText("Still working. Large scans take longer.")).toBeInTheDocument();
  rerender(<Progress status="READING" progress={{ ...reading, done: 4, label: "Reading claim page 4 (4 of 7)" }} />);
  expect(screen.queryByText("Still working. Large scans take longer.")).toBeNull();
});

test("marks the current step", () => {
  render(<Progress status="CHECKING" progress={null} />);
  expect(screen.getByText("Checking")).toHaveAttribute("aria-current", "step");
});
