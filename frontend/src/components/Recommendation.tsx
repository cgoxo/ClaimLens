import type { Action, Outcome } from "../api/types";

const LABEL: Record<Action, string> = {
  investigate: "Investigate",
  query: "Query",
  not_payable: "Not payable",
  approve_part: "Approve in part",
  approve: "Approve",
};

const line = (label: string, o: Outcome) => `${label}: ${o.risk.toUpperCase()} · ${o.score}`;

/** The reviewer's recommendation, with the first run's verdict beside it once reviews have changed things. */
export default function Recommendation({ analysis, current }: { analysis: Outcome | null | undefined; current: Outcome | null | undefined }) {
  const shown = current ?? analysis;
  const rec = shown?.recommendation;
  if (!shown || !rec) return null;
  const changed = !!analysis && !!current
    && (analysis.recommendation?.action !== current.recommendation?.action || analysis.score !== current.score);
  return (
    <div className="recommendation">
      <span className={`rec-badge rec-${rec.action}`}>{LABEL[rec.action]}</span>
      {rec.reasons.length > 0 && <ul className="rec-reasons">{rec.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
      {changed && <p className="rec-change mono">{`${line("Analysis", analysis)} → ${line("After review", current)}`}</p>}
    </div>
  );
}
