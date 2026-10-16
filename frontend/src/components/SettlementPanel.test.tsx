import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rule, settlement } from "../test/outcome";
import SettlementPanel from "./SettlementPanel";

test("shows a deduction with its reason and amount, and its clause chip opens the clause", async () => {
  const onOpenClause = vi.fn();
  render(<SettlementPanel settlement={settlement} onOpenClause={onOpenClause} />);
  expect(screen.getByText("Room rent above the ₹3,000/day limit")).toBeInTheDocument();
  expect(screen.getAllByText("₹4,500").length).toBeGreaterThan(0);
  await userEvent.click(screen.getByRole("button", { name: "policy p.2" }));
  expect(onOpenClause).toHaveBeenCalledWith(rule);
});

test("shows the co-pay row, the payable total and the notes", () => {
  render(<SettlementPanel settlement={settlement} onOpenClause={vi.fn()} />);
  expect(screen.getByText("Co-pay 10%")).toBeInTheDocument();
  expect(screen.getByRole("row", { name: /^Payable/ })).toHaveTextContent("₹27,000");
  expect(screen.getByText("One bill has no date and was left out.")).toBeInTheDocument();
});

test("shows a capped row when the bills come to more than was claimed", () => {
  const capped = { ...settlement, claimed: 25000, subtotal: 25000, co_pay: null, payable: 25000 };
  render(<SettlementPanel settlement={capped} onOpenClause={vi.fn()} />);
  // admissible bills 9,000 + 22,000 = 31,000; claimed 25,000
  expect(screen.getByRole("row", { name: /Capped at the claimed amount/ })).toHaveTextContent("₹6,000");
});

test("no capped row when the bills fit the claim", () => {
  render(<SettlementPanel settlement={{ ...settlement, subtotal: 31000 }} onOpenClause={vi.fn()} />);
  expect(screen.queryByText("Capped at the claimed amount")).toBeNull();
});
