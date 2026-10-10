import { useState } from "react";
import type { Finding, Review } from "../api/types";
import { citationLabel } from "../lib/findings";

interface Props {
  finding: Finding;
  number: number;
  selected: boolean;
  onSelect(): void;
  onReview(action: "accept" | "dismiss", note: string): Promise<Finding>;
}

const money = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export default function FindingCard({ finding, number, selected, onSelect, onReview }: Props) {
  const [review, setReview] = useState<Review | null>(finding.review);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(action: "accept" | "dismiss") {
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
            {review.action === "accept" ? "Accepted" : "Dismissed"} by {review.by}
            {review.note && <> · “{review.note}”</>}
          </p>
        ) : selected && (
          <div className="finding-actions">
            <input aria-label="Review note" placeholder="Note (optional)" value={note}
              onChange={(e) => setNote(e.target.value)} disabled={saving} />
            <button className="btn btn-accept" disabled={saving} onClick={() => void act("accept")}>Accept</button>
            <button className="btn btn-quiet" disabled={saving} onClick={() => void act("dismiss")}>Dismiss</button>
          </div>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </article>
  );
}
