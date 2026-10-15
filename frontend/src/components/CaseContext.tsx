import type { ReactNode } from "react";
import type { CaseContextData, Citation, Fact } from "../api/types";
import { daysBetween, money } from "../lib/format";

interface Props {
  context: CaseContextData;
  /** a policy_number_mismatch finding exists: mark both numbers */
  mismatch: boolean;
  onOpen(c: Citation): void;
}

type Facts = Record<string, unknown>;
type Doc = "claim" | "policy";

const fact = (facts: Facts | null, key: string) => (facts?.[key] ?? null) as Fact | null;
const text = (f: Fact | null) => (f && f.value !== null ? String(f.value) : null);
const amount = (f: Fact | null) => (f && typeof f.value === "number" ? money(f.value) : text(f));
const MISSING = <span className="muted">Not found in documents</span>;

function PageLink({ label, doc, page, quote, bbox, onOpen }: {
  label: string; doc: Doc; page: number; quote: string; bbox: Citation["bbox"]; onOpen(c: Citation): void;
}) {
  return (
    <button type="button" className="page-link mono" aria-label={`${label}, ${doc} page ${page}`}
      onClick={() => onOpen({ doc, page, quote, bbox, source: "page" })}>
      p.{page} ↗
    </button>
  );
}

function Row({ label, children, warn = false }: { label: string; children: ReactNode; warn?: boolean }) {
  return (
    <div className={`ctx-row${warn ? " is-warning" : ""}`}>
      <dt>{label}</dt>
      <dd>{children ?? MISSING}</dd>
    </div>
  );
}

export default function CaseContext({ context, mismatch, onOpen }: Props) {
  const { claim, policy } = context;

  // one fact, shown with a link to its page
  const show = (doc: Doc, facts: Facts | null, key: string, label: string, warn = false, format = text) => {
    const f = fact(facts, key);
    const value = format(f);
    return (
      <Row label={label} warn={warn}>
        {f && value !== null ? (
          <><span>{value}</span> <PageLink label={label} doc={doc} page={f.page} quote={f.quote} bbox={f.bbox} onOpen={onOpen} /></>
        ) : null}
      </Row>
    );
  };

  const admitted = text(fact(claim, "admission_date"));
  const discharged = text(fact(claim, "discharge_date"));
  const days = admitted && discharged ? daysBetween(admitted, discharged) : null;
  const procedures = (claim?.procedures ?? []) as { name: Fact; date?: Fact }[];
  const bills = (claim?.bills ?? []) as { kind: string; total?: Fact; page: number }[];
  const waits = (policy?.waiting_periods ?? []) as { condition: string; months: number; clause: string; page: number; quote: string }[];
  const age = context.policy_age_months;

  return (
    <section className="case-context" aria-label="What this claim is about">
      <div className="ctx-card">
        <h2>The claim</h2>
        <dl>
          {show("claim", claim, "claimant_name", "Patient")}
          {show("claim", claim, "hospital_name", "Hospital")}
          {show("claim", claim, "diagnosis", "Diagnosis")}
          <Row label="Stay">
            {admitted && discharged ? <span>{admitted} → {discharged}{days !== null && ` (${days} days)`}</span> : null}
          </Row>
          <Row label="Procedure">
            {procedures.length ? procedures.map((p, i) => (
              <span key={i} className="ctx-line">
                {String(p.name.value)}{p.date ? `, ${p.date.value}` : ""}{" "}
                <PageLink label={`Procedure ${i + 1}`} doc="claim" page={p.name.page} quote={p.name.quote} bbox={p.name.bbox} onOpen={onOpen} />
              </span>
            )) : null}
          </Row>
          {show("claim", claim, "amount_claimed", "Claimed", false, amount)}
          <Row label="Bills">
            {bills.length ? bills.map((b, i) => (
              <span key={i} className="ctx-line">
                <span className="ctx-kind">{b.kind}</span> {amount(b.total ?? null) ?? "total not found"}{" "}
                {b.total && <PageLink label={`Bill ${i + 1}`} doc="claim" page={b.total.page} quote={b.total.quote} bbox={b.total.bbox} onOpen={onOpen} />}
              </span>
            )) : null}
          </Row>
          {show("claim", claim, "policy_number", "Policy number", mismatch)}
        </dl>
      </div>

      <div className="ctx-card">
        <h2>The policy</h2>
        <dl>
          {show("policy", policy, "insurer_name", "Insurer")}
          {show("policy", policy, "policy_number", "Policy number", mismatch)}
          {show("policy", policy, "start_date", "Start date")}
          {show("policy", policy, "sum_insured", "Sum insured", false, amount)}
          {show("policy", policy, "room_rent_limit_per_day", "Room limit / day", false, amount)}
          <Row label="Waiting periods">
            {waits.length ? waits.map((w, i) => (
              <span key={i} className="ctx-line">
                <span>{`${w.condition} · ${w.months} months${w.clause ? ` · clause ${w.clause}` : ""}`}</span>{" "}
                <PageLink label={`Waiting period ${i + 1}`} doc="policy" page={w.page} quote={w.quote} bbox={null} onOpen={onOpen} />
              </span>
            )) : null}
          </Row>
          <Row label="Policy age at treatment">{age !== null ? <span>{age} months</span> : null}</Row>
        </dl>
      </div>
    </section>
  );
}
