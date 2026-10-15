import { render, screen, within } from "@testing-library/react";
import type { Client } from "../api/client";
import type { CaseCard, PageMeta } from "../api/types";
import PageViewer from "./PageViewer";

const page = (n: number, card_id: string | null, doc = "claim"): PageMeta =>
  ({ doc, page: n, kind: "digital", width: 600, height: 800, card_id });
const card = (id: string, label: string, role: CaseCard["role"] = "bill"): CaseCard =>
  ({ id, role, kind: null, label, files: [] });
const client = { pageImageUrl: vi.fn(async () => "blob:x") } as unknown as Client;

function show(pages: PageMeta[], cards: CaseCard[]) {
  render(<PageViewer caseId="c1" pages={pages} cards={cards} client={client} selected={null}
    selectedNumber={null} selectedDetail="" />);
}

test("claim pages are grouped under their cards", () => {
  show([page(1, "claim-form"), page(2, "b1"), page(3, "b2"), page(4, "b2")],
    [card("claim-form", "Claim form", "claim_form"), card("b1", "Bill 1 · hospital"), card("b2", "Bill 2 · pharmacy")]);
  const group = screen.getByRole("group", { name: "Bill 2 · pharmacy" });
  expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["3", "4"]);
  expect(screen.getByRole("group", { name: "Claim form" })).toBeInTheDocument();
});

test("a case from before cards shows one group per document", () => {
  show([page(1, null), page(2, null)], []);
  const group = screen.getByRole("group", { name: "Claim" });
  expect(within(group).getAllByRole("button")).toHaveLength(2);
});
