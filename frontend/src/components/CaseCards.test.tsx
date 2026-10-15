import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { DraftCard } from "../lib/upload";
import CaseCards, { startingCards } from "./CaseCards";

let latest: DraftCard[] = [];

function Harness() {
  const [cards, setCards] = useState(startingCards());
  latest = cards;
  return <CaseCards cards={cards} onChange={setCards} busy={false} errors={new Map()} />;
}

const pdf = (name: string) => new File(["%PDF"], name, { type: "application/pdf" });
const claimFiles = () => latest.find((c) => c.id === "claim")!.files.map((f) => f.name);

test("two forms: the claim and the policy", () => {
  render(<Harness />);
  expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Claim", "Policy"]);
  expect(screen.queryByRole("button", { name: /Add bill/ })).toBeNull();
  expect(screen.getByText(/claim form, supporting documents and the bill/i)).toBeInTheDocument();
});

test("files can be added, reordered and removed", async () => {
  render(<Harness />);
  await userEvent.upload(screen.getByLabelText("Add files to Claim"), [pdf("bill-1.pdf"), pdf("bill-2.pdf")]);
  expect(claimFiles()).toEqual(["bill-1.pdf", "bill-2.pdf"]);
  await userEvent.click(screen.getByRole("button", { name: "Move bill-2.pdf up" }));
  expect(claimFiles()).toEqual(["bill-2.pdf", "bill-1.pdf"]);
  await userEvent.click(screen.getByRole("button", { name: "Remove bill-2.pdf" }));
  expect(claimFiles()).toEqual(["bill-1.pdf"]);
});

test("a wrong file type is refused with a message on its form", async () => {
  render(<Harness />);
  await userEvent.upload(screen.getByLabelText("Add files to Policy"), new File(["x"], "notes.docx"), {
    applyAccept: false });
  const card = screen.getByRole("heading", { name: "Policy" }).closest("section")!;
  expect(within(card).getByRole("alert")).toHaveTextContent("notes.docx: Must be a PDF, JPG or PNG");
  expect(latest.find((c) => c.id === "policy")!.files).toEqual([]);
});

test("an upload error shows under its file", () => {
  const cards = startingCards();
  const bad = pdf("bad.pdf");
  cards[0].files = [bad];
  render(<CaseCards cards={cards} onChange={vi.fn()} busy={false} errors={new Map([[bad, "not a readable PDF"]])} />);
  expect(screen.getByText("not a readable PDF")).toBeInTheDocument();
});
