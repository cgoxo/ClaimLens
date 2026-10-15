import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { CaseSummary } from "../api/types";
import CaseTable from "./CaseTable";

const base: CaseSummary = { id: "a1", status: "READY", risk: "low", score: 5, created_at: "2026-10-16T10:00:00Z",
  progress: null, findings_count: 1, unseen: false };

const show = (cases: CaseSummary[]) => render(<MemoryRouter><CaseTable cases={cases} /></MemoryRouter>);

test("a case that finished while away has a new dot", () => {
  show([{ ...base, unseen: true }, { ...base, id: "b2" }]);
  expect(screen.getAllByLabelText("new")).toHaveLength(1);
});

test("a running case shows a live status chip", () => {
  show([{ ...base, status: "READING", risk: null, score: null,
    progress: { step: "READING", done: 2, total: 7, label: "Reading claim page 2 (2 of 7)" } }]);
  expect(screen.getByText("Reading…")).toHaveClass("chip");
});
