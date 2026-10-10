import { Link } from "react-router-dom";
import type { CaseSummary } from "../api/types";
import RiskStamp from "./RiskStamp";

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function CaseTable({ cases }: { cases: CaseSummary[] }) {
  if (cases.length === 0) return <p className="muted">No cases yet. Open one above, or try the sample.</p>;
  const sorted = [...cases].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <table className="case-table">
      <thead>
        <tr><th>Case</th><th>Opened</th><th>Status</th><th>Risk</th><th className="num">Score</th></tr>
      </thead>
      <tbody>
        {sorted.map((c) => (
          <tr key={c.id}>
            <td><Link className="mono" to={`/cases/${c.id}`}>{c.id}</Link></td>
            <td>{when(c.created_at)}</td>
            <td>{c.status.toLowerCase()}</td>
            <td>{c.risk ? <RiskStamp risk={c.risk} score={c.score} small /> : "–"}</td>
            <td className="num mono">{c.score ?? "–"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
