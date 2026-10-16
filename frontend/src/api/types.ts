// Mirrors the backend JSON (backend/claimlens/models.py and api.py).

export type Severity = "critical" | "high" | "medium" | "low" | "coverage";
export type Status = "DRAFT" | "QUEUED" | "READING" | "CHECKING" | "PROVING" | "READY" | "FAILED" | "REJECTED";

/** A file that stopped the case: not an insurance document, or in the wrong form. */
export interface RejectedFile {
  name: string;
  form: string;
  reason: string;
  page: number;
  quote: string;
}
export type CardRole = "claim" | "policy";

/** One of the two upload forms: the claim (claim form, supporting documents, the bill) or the policy. */
export interface CardSpec {
  id: string;
  role: CardRole;
}

export interface CaseCard extends CardSpec {
  label: string;
  files: { name: string; pages: number }[];
}
export type Risk = "low" | "review" | "high";
export type BBox = [number, number, number, number];

export interface Citation {
  doc: string;
  page: number;
  quote: string;
  bbox: BBox | null;
  source: "page" | "metadata" | "hidden_layer";
}

export interface Review {
  action: "accept" | "dismiss" | "restore";
  note: string;
  by: string;
  at: string;
}

/** Rupees a finding takes off a bill line; bill/line -1 means the whole bill or the claim level. */
export interface LineDeduction {
  bill: number;
  line: number;
  amount: number;
}

export interface Deduction {
  amount: number;
  reason: string;
  finding_id: string | null;
  rule: Citation | null;
}

export type BillCategory = "room" | "icu" | "surgery" | "doctor" | "nursing" | "investigations" | "medicines"
  | "consumables" | "implants" | "ambulance" | "other";

export interface SettlementLine {
  bill: number;
  line: number;
  desc: string;
  category: BillCategory;
  claimed: number;
  deductions: Deduction[];
  payable: number;
}

export interface SettlementNote {
  text: string;
  affects_amount: boolean;
}

export interface Settlement {
  lines: SettlementLine[];
  claimed: number | null;
  whole_claim: Deduction | null;
  claim_level: Deduction[];
  subtotal: number;
  sub_limit: Deduction | null;
  deductible: Deduction | null;
  co_pay: Deduction | null;
  si_cap: Deduction | null;
  payable: number | null;
  notes: SettlementNote[];
}

export type Action = "investigate" | "query" | "not_payable" | "approve_part" | "approve";

export interface Recommendation {
  action: Action;
  reasons: string[];
}

export interface Outcome {
  score: number;
  risk: Risk;
  payable: number | null;
  recommendation: Recommendation | null;
  settlement: Settlement | null;
}

export interface RuleNotVerified {
  rule: string;
  clause: string;
  page: number;
  quote: string;
}

export interface Finding {
  id: string;
  check: "tamper" | "story" | "duplicate" | "cards" | "coverage" | "bill_story";
  code: string;
  severity: Severity;
  title: string;
  detail: string;
  citations: Citation[];
  amount_not_payable: number;
  deductions?: LineDeduction[];
  items: string[];
  verified: boolean;
  review: Review | null;
  /** no longer produced after a fact correction: never counts, hidden in the UI */
  removed?: boolean;
}

export interface PageMeta {
  doc: string;
  page: number;
  kind: "digital" | "scanned" | "scanned_with_text" | "image" | "unreadable";
  width: number;
  height: number;
  card_id: string | null;
  file_index: number;
}

export interface Fact {
  value: string | number | null;
  /** "reviewer" once a reviewer corrected it through chat */
  source?: "document" | "reviewer";
  page: number;
  quote: string;
  bbox: BBox | null;
}

export interface CaseProgress {
  step: Status;
  done: number;
  total: number;
  label: string;
}

/** Grounded claim and policy facts (backend ClaimFacts / PolicyFacts as JSON, nulls left out). */
export interface CaseContextData {
  claim: Record<string, unknown> | null;
  policy: Record<string, unknown> | null;
  policy_age_months: number | null;
}

export interface Case {
  id: string;
  owner_email: string;
  status: Status;
  step: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  files: Record<string, string>;
  score: number | null;
  risk: Risk | null;
  payable: number | null;
  summary: string | null;
  dropped_findings: { title: string; reason: string }[];
  context: CaseContextData | null;
  rejected?: RejectedFile[];
  cards: CaseCard[];
  progress: CaseProgress | null;
  finished_at: string | null;
  seen_at: string | null;
  findings_count: number | null;
  findings: Finding[];
  pages: PageMeta[];
  /** what the first run decided; null on cases analysed before the rulebook */
  analysis?: Outcome | null;
  /** after the reviewer's accepts and dismissals */
  current?: Outcome | null;
  rules_not_verified?: RuleNotVerified[];
}

export interface CaseSummary {
  id: string;
  status: Status;
  risk: Risk | null;
  score: number | null;
  created_at: string;
  progress: CaseProgress | null;
  findings_count: number | null;
  unseen: boolean;
}

/** One saved state of a finding, from GET …/findings/{fid}/versions. */
export interface FindingVersion {
  version: number;
  action: string;
  by: string;
  at: string;
  note: string;
  finding: Finding;
}

// --- chat ---

export interface Box {
  doc: string;
  page: number;
  bbox: BBox;
}

export type ProposalStatus = "pending" | "applying" | "applied" | "ignored" | "stale" | "failed";

export interface Proposal {
  id: string;
  type: "review_finding" | "set_severity" | "add_finding" | "correct_fact";
  reason: string;
  finding_id: string | null;
  action: "accept" | "dismiss" | "restore" | null;
  severity: Severity | null;
  title: string;
  detail: string;
  citations: Citation[];
  path: string | null;
  value: string | number | null;
  evidence: Box | null;
  finding_version: number | null;
  status: ProposalStatus;
  decided_by: string | null;
  decided_at: string | null;
  error: string | null;
}

export interface ChatMessage {
  id: string;
  role: "reviewer" | "assistant";
  text: string;
  selection: Box | null;
  citations: Citation[];
  proposals: Proposal[];
  tool_calls: Record<string, unknown>[];
  verified: boolean;
  notes: string[];
  by: string;
  created_at: string;
}

export interface ChatThread {
  id: string;
  status: "active" | "closed";
  carried_summary: string;
  summary: string;
  created_by: string;
  created_at: string;
}

export interface ChatState {
  thread: ChatThread | null;
  messages: ChatMessage[];
  previous: { id: string; summary: string; created_at: string }[];
}
