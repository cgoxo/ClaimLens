import type { ChatMessage, Citation, Proposal } from "../api/types";

export const cite: Citation = { doc: "claim", page: 3, quote: "Rs 48,500", bbox: [1, 2, 3, 4], source: "page" };

export const proposal = (over: Partial<Proposal> = {}): Proposal => ({
  id: "p1", type: "review_finding", reason: "It is a scanner artefact.", finding_id: "f1", action: "dismiss",
  severity: null, title: "", detail: "", citations: [], path: null, value: null, evidence: null,
  finding_version: 1, status: "pending", decided_by: null, decided_at: null, error: null, ...over,
});

export const message = (over: Partial<ChatMessage> = {}): ChatMessage => ({
  id: "m1", role: "assistant", text: "The total is Rs 48,500.", selection: null, citations: [cite], proposals: [],
  tool_calls: [], verified: true, notes: [], by: "assistant", created_at: "2026-10-16T10:00:00Z", ...over,
});
