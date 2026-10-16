import { useState } from "react";
import type { Proposal } from "../api/types";

interface Props {
  proposal: Proposal;
  /** the title of the finding the proposal is about (review and severity proposals name it by id) */
  findingTitle?: string;
  onDecide(action: "apply" | "ignore"): Promise<unknown>;
}

function describe(p: Proposal, findingTitle: string): string {
  const target = findingTitle || p.finding_id || "";
  switch (p.type) {
    case "review_finding": {
      const verb = p.action === "dismiss" ? "Dismiss" : p.action === "restore" ? "Restore" : "Accept";
      return `${verb}: ${target}`;
    }
    case "set_severity": return `Change severity to ${p.severity}: ${target}`;
    case "add_finding": return `Add finding: ${p.title}`;
    case "correct_fact": return `Correct ${p.path} to ${p.value}`;
  }
}

function statusText(p: Proposal): string | null {
  switch (p.status) {
    case "applied": return "Applied";
    case "ignored": return "Ignored";
    case "applying": return "Applying…";
    case "stale": return "Changed since — ask again";
    case "failed": return `Failed: ${p.error ?? "unknown error"}`;
    default: return null;
  }
}

export default function ProposalCard({ proposal, findingTitle = "", onDecide }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (action: "apply" | "ignore") => {
    setBusy(true);
    setError(null);
    try {
      await onDecide(action);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the decision");
    } finally {
      setBusy(false);
    }
  };

  const status = statusText(proposal);
  return (
    <div className={`proposal status-${proposal.status}`}>
      <p className="proposal-what">{describe(proposal, findingTitle)}</p>
      {proposal.reason && <p className="proposal-reason muted small">{proposal.reason}</p>}
      {status ? (
        <p className="proposal-status small" role="status">{status}</p>
      ) : (
        <div className="proposal-actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void decide("apply")}>Apply</button>
          <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => void decide("ignore")}>Ignore</button>
        </div>
      )}
      {error && <p className="proposal-error small" role="alert">{error}</p>}
    </div>
  );
}
