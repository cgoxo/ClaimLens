import type { BBox } from "../api/types";

/** A PDF-point box as percentages of the page, so a marker scales with the page image. */
export function toPercentBox([x0, y0, x1, y1]: BBox, pageWidth: number, pageHeight: number) {
  return {
    left: (x0 / pageWidth) * 100,
    top: (y0 / pageHeight) * 100,
    width: ((x1 - x0) / pageWidth) * 100,
    height: ((y1 - y0) / pageHeight) * 100,
  };
}
