import type { Citation, Finding } from "../api/types";
import { citationLabel, groupFindings } from "./findings";

const f = (id: string, severity: Finding["severity"]): Finding => ({
  id, severity, check: "story", code: id, title: id, detail: "", citations: [],
  amount_not_payable: 0, items: [], verified: true, review: null,
});

test("groups in severity order, skipping empty groups and keeping order inside a group", () => {
  const groups = groupFindings([f("c1", "coverage"), f("l1", "low"), f("k1", "critical"), f("h1", "high"), f("k2", "critical")]);
  expect(groups.map(([s]) => s)).toEqual(["critical", "high", "low", "coverage"]);
  expect(groups[0][1].map((x) => x.id)).toEqual(["k1", "k2"]);
});

test("citation labels", () => {
  const c = (source: Citation["source"]): Citation => ({ doc: "claim", page: 3, quote: "q", bbox: null, source });
  expect(citationLabel(c("page"))).toBe("claim p.3");
  expect(citationLabel(c("metadata"))).toBe("file properties");
  expect(citationLabel(c("hidden_layer"))).toBe("claim p.3 · hidden text");
});
