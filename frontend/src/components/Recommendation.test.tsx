import { render, screen } from "@testing-library/react";
import { outcome } from "../test/outcome";
import Recommendation from "./Recommendation";

test("shows the badge and the reasons", () => {
  render(<Recommendation analysis={outcome()} current={outcome()} />);
  expect(screen.getByText("Approve in part")).toBeInTheDocument();
  expect(screen.getByText("Room rent is above the limit.")).toBeInTheDocument();
  expect(screen.queryByText(/After review/)).toBeNull();
});

test("shows analysis against after-review when they differ", () => {
  const current = outcome({ score: 30, risk: "review", recommendation: { action: "query", reasons: ["x"] } });
  render(<Recommendation analysis={outcome()} current={current} />);
  expect(screen.getByText("Query")).toBeInTheDocument();
  expect(screen.getByText("Analysis: HIGH · 70 → After review: REVIEW · 30")).toBeInTheDocument();
});

test("shows nothing when there is no recommendation", () => {
  const { container } = render(<Recommendation analysis={null} current={outcome({ recommendation: null, settlement: null })} />);
  expect(container).toBeEmptyDOMElement();
});
