import type { Citation, Finding, Severity } from "../api/types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "coverage"];

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  coverage: "Coverage",
};

export function groupFindings(findings: Finding[]): [Severity, Finding[]][] {
  return SEVERITY_ORDER.map((s) => [s, findings.filter((f) => f.severity === s)] as [Severity, Finding[]]).filter(
    ([, group]) => group.length > 0,
  );
}

export function citationLabel(c: Citation): string {
  if (c.source === "metadata") return "file properties";
  const base = `${c.doc} p.${c.page}`;
  return c.source === "hidden_layer" ? `${base} · hidden text` : base;
}
