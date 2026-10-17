import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import type { Client } from "../api/client";
import type { Box, ChatMessage, ChatState, Citation, Finding, Outcome } from "../api/types";
import ProposalCard from "./ProposalCard";

interface Props {
  caseId: string;
  client: Pick<Client, "getChat" | "ask" | "newChat" | "decide">;
  onOpenCitation(c: Citation): void;
  /** called after Apply; `current` is null when the server could not recalculate, so the caller refetches */
  onOutcome(current: Outcome | null): void;
  pendingSelection: Box | null;
  onClearSelection(): void;
  /** to name the finding a proposal is about */
  findings?: Pick<Finding, "id" | "title">[];
  /** chat is turned off on the server (404): the caller hides the tab */
  onUnavailable?(): void;
  /** the panel stays mounted when its tab is not shown, so a draft and a pending answer survive */
  hidden?: boolean;
}

const UNAVAILABLE = "Couldn't answer right now, try again";

export default function ChatPanel({ caseId, client, onOpenCitation, onOutcome, pendingSelection, onClearSelection, findings = [], onUnavailable, hidden = false }: Props) {
  const [state, setState] = useState<Pick<ChatState, "messages" | "previous"> | null>(null);
  const [off, setOff] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    client.getChat(caseId).then(
      (s) => { if (live) setState({ messages: s.messages, previous: s.previous }); },
      (e) => {
        if (!live) return;
        if (e instanceof ApiError && e.status === 404) { setOff(true); onUnavailable?.(); }
        else setLoadError(e instanceof ApiError ? e.detail : "Couldn't load the chat");
      },
    );
    return () => { live = false; };
  }, [caseId, client]);

  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [state?.messages.length, waiting]);

  if (off) return null;
  if (hidden && !state) return null;
  if (loadError) return <p className="chat-error" role="alert" hidden={hidden}>{loadError}</p>;
  if (!state) return <p className="loading">Opening the chat…</p>;

  const append = (...added: ChatMessage[]) =>
    setState((s) => s && { ...s, messages: [...s.messages, ...added] });

  const send = async () => {
    const question = text.trim();
    if (!question || waiting) return;
    const sent: ChatMessage = {
      id: `local-${Date.now()}`, role: "reviewer", text: question, selection: pendingSelection, citations: [],
      proposals: [], tool_calls: [], verified: true, notes: [], by: "", created_at: new Date().toISOString(),
    };
    setWaiting(true);
    setError(null);
    append(sent);
    try {
      const reply = await client.ask(caseId, question, pendingSelection);
      append(reply);
      setText("");
      if (pendingSelection) onClearSelection();
    } catch (e) {
      setState((s) => s && { ...s, messages: s.messages.filter((m) => m.id !== sent.id) });
      setError(e instanceof ApiError && e.status !== 503 ? e.detail : UNAVAILABLE); // the text stays in the box
    } finally {
      setWaiting(false);
    }
  };

  const newChat = async () => {
    setError(null);
    try {
      await client.newChat(caseId);
      setState((s) => s && { ...s, messages: [] });
      client.getChat(caseId).then((s) => setState((cur) => cur && { ...cur, previous: s.previous }), () => {});
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Couldn't start a new chat");
    }
  };

  const decide = async (pid: string, action: "apply" | "ignore") => {
    let result;
    try {
      result = await client.decide(caseId, pid, action);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // decided already (another tab, a double click): show the card's real status
        try {
          const fresh = await client.getChat(caseId);
          setState((s) => s && { ...s, messages: fresh.messages });
        } catch { /* keep what is shown */ }
        throw new Error("Already decided");
      }
      throw e;
    }
    const { proposal, current } = result;
    setState((s) => s && {
      ...s,
      messages: s.messages.map((m) => ({ ...m, proposals: m.proposals.map((p) => (p.id === pid ? proposal : p)) })),
    });
    if (action === "apply") onOutcome(current);
  };

  const titleOf = (id: string | null) => findings.find((f) => f.id === id)?.title ?? "";

  return (
    <section className="chat" aria-label="Chat" hidden={hidden}>
      <div className="chat-head">
        <button type="button" className="btn btn-quiet" onClick={() => void newChat()} disabled={waiting}>New chat</button>
      </div>
      {state.previous.length > 0 && (
        <details className="chat-previous">
          <summary>Previous chats ({state.previous.length})</summary>
          <ul>
            {state.previous.map((t) => (
              <li key={t.id}><span className="muted small">{new Date(t.created_at).toLocaleDateString()}</span> {t.summary || "No summary"}</li>
            ))}
          </ul>
        </details>
      )}
      <div className="chat-log">
        {state.messages.length === 0 && <p className="muted">Ask about this claim. Answers cite the documents.</p>}
        {state.messages.map((m) => (
          <article key={m.id} className={`chat-msg is-${m.role}${m.role === "assistant" && !m.verified ? " is-unverified" : ""}`}>
            <p className="chat-text">{m.text}</p>
            {m.selection && <p className="muted small">About {m.selection.doc} p.{m.selection.page}</p>}
            {m.role === "assistant" && !m.verified && (
              <p className="chat-unverified small">Couldn't verify against the documents</p>
            )}
            {m.citations.length > 0 && (
              <p className="chat-cites">
                {m.citations.map((c, i) => (
                  <button key={i} type="button" className="page-link mono" title={c.quote} onClick={() => onOpenCitation(c)}>
                    {c.doc} p.{c.page} ↗
                  </button>
                ))}
              </p>
            )}
            {m.notes.map((n, i) => <p key={i} className="chat-note muted small">{n}</p>)}
            {m.proposals.map((p) => (
              <ProposalCard key={p.id} proposal={p} findingTitle={titleOf(p.finding_id)} onDecide={(a) => decide(p.id, a)} />
            ))}
          </article>
        ))}
        {waiting && <p className="chat-thinking muted" role="status">Thinking…</p>}
        <div ref={end} />
      </div>
      {error && <p className="chat-error" role="alert">{error}</p>}
      {pendingSelection && (
        <p className="chat-selection small">
          Asking about {pendingSelection.doc} p.{pendingSelection.page}{" "}
          <button type="button" className="btn-icon" aria-label="Clear selection" onClick={onClearSelection}>×</button>
        </p>
      )}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <textarea value={text} rows={2} maxLength={2000} aria-label="Your question" placeholder="Ask about this claim…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
        <button type="submit" className="btn btn-primary" disabled={waiting || !text.trim()}>Send</button>
      </form>
    </section>
  );
}
