import type { Risk } from "../api/types";

const LABEL: Record<Risk, string> = { high: "High risk", review: "Review", low: "Low risk" };

export default function RiskStamp({ risk, score, small = false }: { risk: Risk; score: number | null; small?: boolean }) {
  return (
    <div className={`stamp stamp-${risk}${small ? " stamp-small" : ""}`} role="img"
      aria-label={`Risk ${risk}, score ${score ?? 0} of 100`}>
      <span className="stamp-word">{LABEL[risk]}</span>
      {!small && <span className="stamp-score mono">{score ?? 0}/100</span>}
    </div>
  );
}
