import { render, screen, within } from "@testing-library/react";
import type { Client } from "../api/client";
import type { CaseCard, PageMeta } from "../api/types";
import PageViewer from "./PageViewer";

const page = (n: number, card_id: string | null, file_index = 0, doc = "claim"): PageMeta =>
  ({ doc, page: n, kind: "digital", width: 600, height: 800, card_id, file_index });
const client = { pageImageUrl: vi.fn(async () => "blob:x") } as unknown as Client;
const claim: CaseCard = { id: "claim", role: "claim", label: "Claim",
  files: [{ name: "claim-form.pdf", pages: 1 }, { name: "hospital-bill-1.jpg", pages: 1 }, { name: "hospital-bill-2.jpg", pages: 1 }] };

function show(pages: PageMeta[], cards: CaseCard[]) {
  render(<PageViewer caseId="c1" pages={pages} cards={cards} client={client} selected={null}
    selectedNumber={null} selectedDetail="" />);
}

test("claim pages are grouped under the file they came from", () => {
  show([page(1, "claim", 0), page(2, "claim", 1), page(3, "claim", 2), page(4, "claim", 2)], [claim]);
  const group = screen.getByRole("group", { name: "hospital-bill-2.jpg" });
  expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["3", "4"]);
  expect(screen.getByRole("group", { name: "claim-form.pdf" })).toBeInTheDocument();
});

test("a case from before cards shows one group per document", () => {
  show([page(1, null), page(2, null)], []);
  expect(within(screen.getByRole("group", { name: "Claim" })).getAllByRole("button")).toHaveLength(2);
});
