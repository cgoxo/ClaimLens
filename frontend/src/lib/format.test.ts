import { daysBetween, money } from "./format";

test("money in Indian grouping", () => {
  expect(money(150000)).toBe("₹1,50,000");
  expect(money(null)).toBe("–");
});

test("days between printed dates", () => {
  expect(daysBetween("10-Mar-2026", "13-Mar-2026")).toBe(3);
  expect(daysBetween("10 March 2026", "13-Mar-2026")).toBe(3);
  expect(daysBetween("2026-03-10", "13-Mar-2026")).toBeNull();
});
