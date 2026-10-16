import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RulebookPanel from "./RulebookPanel";

const policy = {
  co_pays: [{ clause: "5.1", page: 3, quote: "10% co-payment", percent: 10 }],
  room_limit: { clause: "4.2", page: 2, quote: "up to 1% of the sum insured", percent_of_si: 1 },
};

test("one row per rule, each opening its clause", async () => {
  const onOpenClause = vi.fn();
  render(<RulebookPanel policy={policy} notVerified={[]} onOpenClause={onOpenClause} />);
  expect(screen.getByText("Co-pay")).toBeInTheDocument();
  expect(screen.getByText("1% of the sum insured per day")).toBeInTheDocument();
  expect(screen.queryByText("Deductible")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: /cl\. 5\.1/ }));
  expect(onOpenClause).toHaveBeenCalledWith({ doc: "policy", page: 3, quote: "10% co-payment", bbox: null, source: "page" });
});

test("co-pay rows show their condition", () => {
  const p = {
    co_pays: [
      { clause: "5.1", page: 3, quote: "q", percent: 10, applies: "age_over", age: 60 },
      { clause: "5.2", page: 3, quote: "q", percent: 20, applies: "other", condition_text: "for non-network hospitals" },
    ],
    window: { clause: "7", page: 5, quote: "q" },
  };
  render(<RulebookPanel policy={p} notVerified={[]} onOpenClause={vi.fn()} />);
  expect(screen.getByText("10% if the insured is over 60")).toBeInTheDocument();
  expect(screen.getByText("20% for non-network hospitals")).toBeInTheDocument();
  expect(screen.getByText("Not stated")).toBeInTheDocument();
});

test("lists rules that could not be verified", () => {
  render(<RulebookPanel policy={policy} notVerified={[{ rule: "deductible", clause: "6", page: 4, quote: "Rs 5,000" }]} onOpenClause={vi.fn()} />);
  expect(screen.getByText("Rules not verified")).toBeInTheDocument();
  expect(screen.getByText("deductible")).toBeInTheDocument();
});

test("an older policy shows its plain room limit as a Room rent row", () => {
  const p = { room_rent_limit_per_day: { value: 3000, page: 2, quote: "Rs 3,000 per day" } };
  render(<RulebookPanel policy={p} notVerified={[]} onOpenClause={vi.fn()} />);
  expect(screen.getByText("Room rent")).toBeInTheDocument();
  expect(screen.getByText(/3,000 per day/)).toBeInTheDocument();
});
