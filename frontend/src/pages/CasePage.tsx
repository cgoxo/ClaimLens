import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Finding } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import AppHeader from "../components/AppHeader";
import FindingList from "../components/FindingList";
import PageViewer from "../components/PageViewer";
import Progress from "../components/Progress";
import RiskStamp from "../components/RiskStamp";
import { useCasePolling } from "../hooks/useCasePolling";
import { SEVERITY_ORDER } from "../lib/findings";

const money = (n: number | null) => (n === null ? "–" : `₹${n.toLocaleString("en-IN")}`);

export default function CasePage() {
  const { id = "" } = useParams();
  const { client } = useAuth();
  const { data, error, connectionLost } = useCasePolling(id, client);
  const [chosenId, setSelectedId] = useState<string | null>(null);
  const [selectionKey, setSelectionKey] = useState(0);

  useEffect(() => () => client.releaseImages(), [client]);

  // findings in display order (grouped by severity), so numbering and j/k match what is on screen
  const findings = useMemo(
    () => [...(data?.findings ?? [])].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)),
    [data],
  );
  // the first finding is selected from the first render, so the viewer opens straight on its page
  const selectedId = findings.some((f) => f.id === chosenId) ? chosenId : findings[0]?.id ?? null;

  const move = useCallback((step: number) => {
    setSelectedId(() => {
      const i = findings.findIndex((f) => f.id === selectedId);
      const next = Math.min(findings.length - 1, Math.max(0, i + step));
      return findings[next]?.id ?? selectedId;
    });
  }, [findings, selectedId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      if (e.key === "j") move(1);
      if (e.key === "k") move(-1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [move]);

  const review = (f: Finding, action: "accept" | "dismiss", note: string) => client.review(id, f.id, action, note);

  let body;
  if (error?.status === 404) {
    body = (
      <div className="notice-card">
        <h1>Case not found</h1>
        <p>This case doesn't exist, or it belongs to someone else.</p>
        <Link to="/" className="btn btn-quiet">← Back to upload</Link>
      </div>
    );
  } else if (error) {
    body = <div className="notice-card"><h1>Couldn't open this case</h1><p>{error.detail}</p></div>;
  } else if (!data) {
    body = <p className="loading">Opening the case file…</p>;
  } else if (data.status === "FAILED") {
    body = (
      <div className="notice-card notice-failed">
        <h1>The investigation stopped</h1>
        <p>Step: <span className="mono">{data.step}</span></p>
        <p className="mono">{data.error}</p>
        <Link to="/" className="btn btn-quiet">Back to upload</Link>
      </div>
    );
  } else if (data.status !== "READY") {
    body = <Progress status={data.status} progress={data.progress} />;
  } else {
    const selected = findings.find((f) => f.id === selectedId) ?? null;
    body = (
      <div className="dossier">
        <section className="dossier-left" aria-label="Findings">
          <header className="case-head">
            <div>
              <h1>Case file</h1>
              <p className="case-id">Case <span className="mono">{data.id}</span> · opened {new Date(data.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</p>
              <dl className="case-facts">
                <div><dt>Payable under policy</dt><dd className="mono">{money(data.payable)}</dd></div>
                <div><dt>Findings</dt><dd className="mono">{findings.length}</dd></div>
              </dl>
            </div>
            {data.risk && <RiskStamp risk={data.risk} score={data.score} />}
          </header>
          {data.summary && <p className="summary">{data.summary}</p>}
          <p className="hint muted">Select a finding to see it on the page. <kbd>j</kbd> / <kbd>k</kbd> to move.</p>
          <FindingList findings={findings} selectedId={selectedId} onSelect={(f) => { setSelectedId(f.id); setSelectionKey((k) => k + 1); }} onReview={review} />
          {data.dropped_findings.length > 0 && (
            <details className="dropped">
              <summary>Not proven ({data.dropped_findings.length})</summary>
              <ul>{data.dropped_findings.map((d, i) => <li key={i}><strong>{d.title}</strong>: {d.reason}</li>)}</ul>
            </details>
          )}
        </section>
        <section className="dossier-right" aria-label="Document viewer">
          <PageViewer caseId={data.id} pages={data.pages} client={client}
            selected={selected?.citations[0] ?? null} selectionKey={selectionKey}
            selectedNumber={selected ? findings.indexOf(selected) + 1 : null}
            selectedDetail={selected?.detail ?? ""} />
        </section>
      </div>
    );
  }

  return (
    <>
      <AppHeader />
      {connectionLost && <div className="connection" role="status">Connection lost, retrying…</div>}
      <main className="page case-page">{body}</main>
    </>
  );
}
