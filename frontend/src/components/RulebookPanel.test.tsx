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

test("lists rules that could not be verified", () => {
  render(<RulebookPanel policy={policy} notVerified={[{ rule: "deductible", clause: "6", page: 4, quote: "Rs 5,000" }]} onOpenClause={vi.fn()} />);
  expect(screen.getByText("Rules not verified")).toBeInTheDocument();
  expect(screen.getByText("deductible")).toBeInTheDocument();
});
