import type { Finding, FindingVersion } from "../api/types";
import { SEVERITY_LABEL, groupFindings } from "../lib/findings";
import FindingCard from "./FindingCard";

interface Props {
  findings: Finding[];
  selectedId: string | null;
  onSelect(f: Finding): void;
  onReview(f: Finding, action: "accept" | "dismiss" | "restore", note: string): Promise<Finding>;
  loadVersions?(f: Finding): Promise<FindingVersion[]>;
}

export default function FindingList({ findings, selectedId, onSelect, onReview, loadVersions }: Props) {
  if (findings.length === 0) return <p className="muted">No problems found that could be proven from the documents.</p>;
  const numberOf = new Map(findings.map((f, i) => [f.id, i + 1]));
  return (
    <div className="finding-groups">
      {groupFindings(findings).map(([severity, group]) => (
        <section key={severity} className={`finding-group group-${severity}`}>
          <h3 className="group-title">{SEVERITY_LABEL[severity]} ({group.length})</h3>
          {group.map((f) => (
            <FindingCard key={f.id} finding={f} number={numberOf.get(f.id)!} selected={f.id === selectedId}
              onSelect={() => onSelect(f)} onReview={(action, note) => onReview(f, action, note)}
              loadVersions={loadVersions && (() => loadVersions(f))} />
          ))}
        </section>
      ))}
    </div>
  );
}
