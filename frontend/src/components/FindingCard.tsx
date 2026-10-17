import { useState } from "react";
import type { Finding, FindingVersion, Review } from "../api/types";
import { citationLabel } from "../lib/findings";

interface Props {
  finding: Finding;
  number: number;
  selected: boolean;
  onSelect(): void;
  onReview(action: "accept" | "dismiss" | "restore", note: string): Promise<Finding>;
  /** loads the finding's saved versions; without it there is no History link */
  loadVersions?(): Promise<FindingVersion[]>;
}

const ACTION_WORDS: Record<string, string> = {
  analysis: "Found by the analysis", accept: "Accepted", dismiss: "Dismissed", restore: "Restored",
  severity: "Severity changed", added: "Added", removed_by_correction: "Removed after a corrected fact",
};
const actionWords = (a: string) => ACTION_WORDS[a] ?? a.replace(/_/g, " ");

const money = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export default function FindingCard({ finding, number, selected, onSelect, onReview, loadVersions }: Props) {
  const [review, setReview] = useState<Review | null>(finding.review);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<{ open: boolean; rows: FindingVersion[] | null; failed: boolean }>(
    { open: false, rows: null, failed: false });

  async function loadHistory() {
    setHistory({ open: true, rows: null, failed: false });
    try {
      setHistory({ open: true, rows: await loadVersions!(), failed: false });
    } catch {
      setHistory({ open: true, rows: null, failed: true });
    }
  }

  async function act(action: "accept" | "dismiss" | "restore") {
    const before = review;
    setSaving(true);
    setError(null);
    try {
      const saved = await onReview(action, note);
      setReview(saved.review);
      setNote("");
    } catch {
      setReview(before);
      setError("Couldn't save the review. Try again.");
    } finally {
      setSaving(false);
    }
  }

  const cite = finding.citations[0];
  return (
    <article className={`finding sev-${finding.severity}${selected ? " is-selected" : ""}`}
      aria-current={selected ? "true" : undefined}>
      <div className="finding-num mono" aria-hidden="true">{number}</div>
      <div className="finding-body">
        <button className="finding-title" onClick={onSelect}>{finding.title}</button>
        {finding.detail && <p className="finding-detail">{finding.detail}</p>}
        <div className="finding-meta">
          {cite && <span className={`chip mono chip-${cite.source}`}>{citationLabel(cite)}</span>}
          {finding.amount_not_payable > 0 && (
            <span className="chip chip-amount mono">{money(finding.amount_not_payable)} not payable</span>
          )}
        </div>
        {review ? (
          <p className={`review-note review-${review.action}`}>
            {review.action === "dismiss" ? "Dismissed" : "Accepted"} by {review.by}
            {review.note && <> · “{review.note}”</>}
            {review.action === "dismiss" && (
              <> <button className="btn btn-quiet" disabled={saving} onClick={() => void act("restore")}>Restore</button></>
            )}
          </p>
        ) : selected && (
          <div className="finding-actions">
            <input aria-label="Review note" placeholder="Note (optional)" value={note}
              onChange={(e) => setNote(e.target.value)} disabled={saving} />
            <button className="btn btn-accept" disabled={saving} onClick={() => void act("accept")}>Accept</button>
            <button className="btn btn-quiet" disabled={saving} onClick={() => void act("dismiss")}>Dismiss</button>
          </div>
        )}
        {loadVersions && (
          <div className="finding-history">
            <button type="button" className="btn btn-quiet" aria-expanded={history.open}
              onClick={() => (history.open ? setHistory((h) => ({ ...h, open: false })) : void loadHistory())}>History</button>
            {history.open && history.failed && (
              <p className="form-error" role="alert">
                Couldn't load the history. <button type="button" className="btn btn-quiet" onClick={() => void loadHistory()}>Retry</button>
              </p>
            )}
            {history.open && !history.failed && !history.rows && <p className="muted small" role="status">Loading history…</p>}
            {history.open && history.rows && (
              <ol className="history-list small" aria-label="History">
                {history.rows.map((v) => (
                  <li key={v.version}>
                    <span className="mono">v{v.version}</span> · {actionWords(v.action)} · {v.by} ·{" "}
                    {new Date(v.at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    {v.note && <> · “{v.note}”</>}
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </article>
  );
}
