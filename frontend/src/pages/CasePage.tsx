import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Citation, Finding } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import AppHeader from "../components/AppHeader";
import CaseContext from "../components/CaseContext";
import FindingList from "../components/FindingList";
import PageViewer from "../components/PageViewer";
import Progress from "../components/Progress";
import Recommendation from "../components/Recommendation";
import RulebookPanel from "../components/RulebookPanel";
import SettlementPanel from "../components/SettlementPanel";
import RiskStamp from "../components/RiskStamp";
import { useCasePolling } from "../hooks/useCasePolling";
import { useCaseWatcher } from "../hooks/useCaseWatcher";
import { SEVERITY_ORDER } from "../lib/findings";
import { money } from "../lib/format";


export default function CasePage() {
  const { id = "" } = useParams();
  const { client } = useAuth();
  const { data, error, connectionLost, setData } = useCasePolling(id, client);
  const [chosenId, setSelectedId] = useState<string | null>(null);
  const [selectionKey, setSelectionKey] = useState(0);
  // a context value opened in the viewer; picking a finding clears it
  const [pinned, setPinned] = useState<Citation | null>(null);
  const openFact = (c: Citation) => { setPinned(c); setSelectionKey((k) => k + 1); };

  useEffect(() => () => client.releaseImages(), [client]);

  // the server marks a finished case seen when it is fetched; refresh the list so badges and the tab count follow
  const { refresh } = useCaseWatcher();
  const finished = data?.status === "READY" || data?.status === "FAILED" || data?.status === "REJECTED";
  useEffect(() => {
    if (finished) void refresh(true);
  }, [finished, refresh]);

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

  // the response carries the recalculated outcome: apply it, so the header and panels follow the review
  const review = async (f: Finding, action: "accept" | "dismiss" | "restore", note: string) => {
    const { current, ...saved } = await client.review(id, f.id, action, note);
    if (current) {
      setData((d) => d && {
        ...d, current, score: current.score, risk: current.risk, payable: current.payable,
        findings: d.findings.map((x) => (x.id === saved.id ? saved : x)),
      });
    }
    return saved;
  };

  const viewer = (selected: Finding | null) => data && (
    <PageViewer caseId={data.id} pages={data.pages} cards={data.cards} client={client}
      selected={pinned ?? selected?.citations[0] ?? null} selectionKey={selectionKey}
      selectedNumber={!pinned && selected ? findings.indexOf(selected) + 1 : null}
      selectedDetail={pinned ? pinned.quote : selected?.detail ?? ""} />
  );

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
  } else if (data.status === "REJECTED") {
    body = (
      <div className="notice-card notice-failed">
        <h1>This claim can't be analysed</h1>
        <p>{(data.rejected ?? []).length > 1 ? "These files don't" : "This file doesn't"} belong in this claim,
          so the analysis stopped before it started:</p>
        <ul className="rejected-files">
          {(data.rejected ?? []).map((r) => (
            <li key={`${r.name}-${r.page}`}>
              <strong className="mono">{r.name}</strong> ({r.form} form): {r.reason}
              {r.quote && <span className="muted"> It reads <q>{r.quote}</q>.</span>}
            </li>
          ))}
        </ul>
        <p>Remove {(data.rejected ?? []).length > 1 ? "them" : "it"}, or put it in the right form, and upload the claim again.</p>
        <Link to="/" className="btn btn-primary">Start a new case</Link>
      </div>
    );
  } else if (data.status === "FAILED") {
    body = (
      <div className="notice-card notice-failed">
        <h1>The investigation stopped</h1>
        <p>Step: <span className="mono">{data.step}</span></p>
        <p className="mono">{data.error}</p>
        <Link to="/" className="btn btn-quiet">Back to upload</Link>
      </div>
    );
  } else if (data.status !== "READY" && data.pages.length === 0) {
    body = <Progress status={data.status} progress={data.progress} />;
  } else {
    const ready = data.status === "READY";
    const selected = ready ? findings.find((f) => f.id === selectedId) ?? null : null;
    const settlement = (data.current ?? data.analysis)?.settlement ?? null;
    const mismatch = findings.some((f) => f.code === "policy_number_mismatch");
    const context = data.context && <CaseContext context={data.context} mismatch={mismatch} onOpen={openFact} />;
    body = ready ? (
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
            <div className="case-verdict">
              {data.risk && <RiskStamp risk={data.risk} score={data.score} />}
              <Recommendation analysis={data.analysis} current={data.current} />
            </div>
          </header>
          {data.summary && <p className="summary">{data.summary}</p>}
          {settlement && (
            <details className="panel" open>
              <summary>Settlement</summary>
              <SettlementPanel settlement={settlement} onOpenClause={openFact} />
            </details>
          )}
          {data.context?.policy && (
            <details className="panel">
              <summary>Policy rules</summary>
              <RulebookPanel policy={data.context.policy} notVerified={data.rules_not_verified ?? []} onOpenClause={openFact} />
            </details>
          )}
          {context}
          <p className="hint muted">Select a finding to see it on the page. <kbd>j</kbd> / <kbd>k</kbd> to move.</p>
          <FindingList findings={findings} selectedId={selectedId} onSelect={(f) => { setPinned(null); setSelectedId(f.id); setSelectionKey((k) => k + 1); }} onReview={review} />
          {data.dropped_findings.length > 0 && (
            <details className="dropped">
              <summary>Not proven ({data.dropped_findings.length})</summary>
              <ul>{data.dropped_findings.map((d, i) => <li key={i}><strong>{d.title}</strong>: {d.reason}</li>)}</ul>
            </details>
          )}
        </section>
        <section className="dossier-right" aria-label="Document viewer">
          {viewer(selected)}
        </section>
      </div>
    ) : (
      <div className="dossier">
        <section className="dossier-left" aria-label="Progress">
          <Progress status={data.status} progress={data.progress} />
          {context}
        </section>
        <section className="dossier-right" aria-label="Document viewer">{viewer(null)}</section>
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
