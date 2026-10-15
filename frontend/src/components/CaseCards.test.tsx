import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { DraftCard } from "../lib/upload";
import CaseCards, { startingCards } from "./CaseCards";

let latest: DraftCard[] = [];

function Harness({ initial = startingCards() }: { initial?: DraftCard[] }) {
  const [cards, setCards] = useState(initial);
  latest = cards;
  return <CaseCards cards={cards} onChange={setCards} busy={false} errors={new Map()} />;
}

const pdf = (name: string) => new File(["%PDF"], name, { type: "application/pdf" });

test("starts with a claim form, one hospital bill, supporting documents and the policy", () => {
  render(<Harness />);
  for (const name of ["Claim form", "Bill 1", "Supporting documents", "Policy"])
    expect(screen.getByRole("heading", { name })).toBeInTheDocument();
  expect(screen.getByLabelText("Kind of Bill 1")).toHaveValue("hospital");
});

test("adds bills up to 10, removes one and renumbers", async () => {
  render(<Harness />);
  const add = screen.getByRole("button", { name: "+ Add bill" });
  for (let i = 0; i < 9; i++) await userEvent.click(add);
  expect(screen.getByRole("heading", { name: "Bill 10" })).toBeInTheDocument();
  expect(add).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Remove Bill 2" }));
  expect(screen.queryByRole("heading", { name: "Bill 10" })).toBeNull();
  expect(latest.filter((c) => c.role === "bill")).toHaveLength(9);
});

test("files can be added, reordered and removed", async () => {
  render(<Harness />);
  await userEvent.upload(screen.getByLabelText("Add files to Bill 1"), [pdf("one.pdf"), pdf("two.pdf")]);
  const bill = () => latest.find((c) => c.id === "b1")!.files.map((f) => f.name);
  expect(bill()).toEqual(["one.pdf", "two.pdf"]);
  await userEvent.click(screen.getByRole("button", { name: "Move two.pdf up" }));
  expect(bill()).toEqual(["two.pdf", "one.pdf"]);
  await userEvent.click(screen.getByRole("button", { name: "Remove two.pdf" }));
  expect(bill()).toEqual(["one.pdf"]);
});

test("a wrong file type is refused with a message on its card", async () => {
  render(<Harness />);
  await userEvent.upload(screen.getByLabelText("Add files to Policy"), new File(["x"], "notes.docx"), {
    applyAccept: false });
  const card = screen.getByRole("heading", { name: "Policy" }).closest("section")!;
  expect(within(card).getByRole("alert")).toHaveTextContent("notes.docx: Must be a PDF, JPG or PNG");
  expect(latest.find((c) => c.id === "policy")!.files).toEqual([]);
});

test("the kind of a bill can be changed", async () => {
  render(<Harness />);
  await userEvent.selectOptions(screen.getByLabelText("Kind of Bill 1"), "pharmacy");
  expect(latest.find((c) => c.id === "b1")!.kind).toBe("pharmacy");
});

test("an upload error shows under its file", () => {
  const cards = startingCards();
  const bad = pdf("bad.pdf");
  cards[1].files = [bad];
  render(<CaseCards cards={cards} onChange={vi.fn()} busy={false} errors={new Map([[bad, "not a readable PDF"]])} />);
  expect(screen.getByText("not a readable PDF")).toBeInTheDocument();
});
