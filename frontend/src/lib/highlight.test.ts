import { toPercentBox } from "./highlight";

test("converts a PDF-point box to percentages of the page", () => {
  const b = toPercentBox([220, 330, 280, 345], 595, 842);
  expect(b.left).toBeCloseTo(36.97, 2);
  expect(b.top).toBeCloseTo(39.19, 2);
  expect(b.width).toBeCloseTo(10.08, 2);
  expect(b.height).toBeCloseTo(1.78, 2);
});
