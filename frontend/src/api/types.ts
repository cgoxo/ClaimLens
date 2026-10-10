// Mirrors the backend JSON (backend/claimlens/models.py and api.py).

export type Severity = "critical" | "high" | "medium" | "low" | "coverage";
export type Status = "QUEUED" | "READING" | "CHECKING" | "PROVING" | "READY" | "FAILED";
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
  action: "accept" | "dismiss";
  note: string;
  by: string;
  at: string;
}

export interface Finding {
  id: string;
  check: "tamper" | "story" | "duplicate" | "coverage";
  code: string;
  severity: Severity;
  title: string;
  detail: string;
  citations: Citation[];
  amount_not_payable: number;
  verified: boolean;
  review: Review | null;
}

export interface PageMeta {
  doc: string;
  page: number;
  kind: "digital" | "scanned" | "scanned_with_text" | "image" | "unreadable";
  width: number;
  height: number;
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
  findings: Finding[];
  pages: PageMeta[];
}

export interface CaseSummary {
  id: string;
  status: Status;
  risk: Risk | null;
  score: number | null;
  created_at: string;
}
