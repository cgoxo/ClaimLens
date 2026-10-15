import { useEffect, useState } from "react";
import type { CaseProgress, Status } from "../api/types";

const STEPS: [Status, string][] = [["READING", "Reading"], ["CHECKING", "Checking"], ["PROVING", "Proving"], ["READY", "Ready"]];
const STALL_MS = 60_000;

export default function Progress({ status, progress }: { status: Status; progress: CaseProgress | null }) {
  const current = status === "QUEUED" ? 0 : STEPS.findIndex(([s]) => s === status);
  const [stalled, setStalled] = useState(false);
  const label = progress?.label ?? "";

  // any change of label restarts the clock
  useEffect(() => {
    setStalled(false);
    const timer = setTimeout(() => setStalled(true), STALL_MS);
    return () => clearTimeout(timer);
  }, [label, status]);

  const determinate = progress !== null && progress.total > 0;
  return (
    <div className="progress-card">
      <h1>Investigating…</h1>
      <ol className="progress">
        {STEPS.map(([s, name], i) => (
          <li key={s} className={i < current ? "done" : i === current ? "current" : ""}
            aria-current={i === current ? "step" : undefined}>{name}</li>
        ))}
      </ol>
      <div className={`progress-bar${determinate ? "" : " is-indeterminate"}`} role="progressbar" aria-label="Progress"
        aria-valuemin={determinate ? 0 : undefined} aria-valuemax={determinate ? progress.total : undefined}
        aria-valuenow={determinate ? progress.done : undefined}>
        <span style={determinate ? { width: `${(100 * progress.done) / progress.total}%` } : undefined} />
      </div>
      {label && <p className="progress-label mono">{label}</p>}
      {stalled ? <p className="muted">Still working. Large scans take longer.</p>
        : <p className="muted">Reading every page, checking the story, proving each finding. Usually under a minute.</p>}
    </div>
  );
}
