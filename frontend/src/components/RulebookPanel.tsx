import type { Citation, RuleNotVerified } from "../api/types";
import { citationLabel } from "../lib/findings";
import { money } from "../lib/format";

interface Props {
  policy: Record<string, unknown> | null | undefined;
  notVerified: RuleNotVerified[];
  onOpenClause(c: Citation): void;
}

/** Every rule has `clause`, `page` and `quote`, plus its own fields. */
interface Rule {
  clause?: string;
  page: number;
  quote: string;
  [field: string]: unknown;
}

const num = (v: unknown) => (typeof v === "number" ? v : null);

function limit(r: Rule): string {
  const amount = num(r.amount);
  const percent = num(r.percent_of_si);
  const parts = [amount !== null ? money(amount) : null, percent !== null ? `${percent}% of the sum insured` : null];
  const text = parts.filter(Boolean).join(" or ");
  return text ? `${text} per day` : "Limit not stated";
}

function coPay(r: Rule): string {
  if (r.applies === "age_over" && num(r.age) !== null) return `${r.percent}% if the insured is over ${r.age}`;
  if (r.applies === "other") return `${r.percent}%${r.condition_text ? ` ${r.condition_text}` : ""}`;
  return `${r.percent}%`;
}

const asList = (v: unknown): Rule[] => (Array.isArray(v) ? (v as Rule[]) : []);
const asRule = (v: unknown): Rule[] => (v && typeof v === "object" && !Array.isArray(v) ? [v as Rule] : []);

export default function RulebookPanel({ policy, notVerified, onOpenClause }: Props) {
  const p = policy ?? {};
  const rows: { label: string; text: string; rule: Rule }[] = [
    ...asList(p.co_pays).map((r) => ({ label: "Co-pay", text: coPay(r), rule: r })),
    ...asRule(p.deductible).map((r) => ({ label: "Deductible", text: `${money(num(r.amount))} per ${r.per ?? "claim"}`, rule: r })),
    ...asRule(p.room_limit).map((r) => ({ label: "Room rent", text: limit(r), rule: r })),
    // older cases: only the plain per-day room limit was read (a Fact with a value, not a rule)
    ...(p.room_limit ? [] : asRule(p.room_rent_limit_per_day).map((r) => ({
      label: "Room rent", text: `${typeof r.value === "number" ? money(r.value) : String(r.value)} per day`, rule: r }))),
    ...asRule(p.icu_limit).map((r) => ({ label: "ICU", text: limit(r), rule: r })),
    ...asRule(p.proportionate_deduction).map((r) => ({ label: "Proportionate deduction", text: "Other charges are cut in the same proportion as room rent", rule: r })),
    ...asList(p.sub_limits).map((r) => ({ label: "Sub-limit", text: `${r.applies_to}: ${limit(r).replace(/ per day$/, "")}${num(r.amount) !== null || num(r.percent_of_si) !== null ? ` per ${r.per ?? "claim"}` : ""}`, rule: r })),
    ...asRule(p.initial_waiting).map((r) => ({ label: "Initial waiting", text: `${r.days} days`, rule: r })),
    ...asRule(p.pre_existing).map((r) => ({ label: "Pre-existing conditions", text: `${r.months} months`, rule: r })),
    ...asList(p.waiting_periods).map((r) => ({ label: "Waiting period", text: `${r.condition}: ${r.months} months`, rule: r })),
    ...asList(p.exclusions).map((r) => ({ label: "Exclusion", text: String(r.what), rule: r })),
    ...asRule(p.non_payable).map((r) => ({
      label: "Non-payable items",
      text: [r.standard_list ? "standard list" : null, ...(Array.isArray(r.items) ? (r.items as string[]) : [])].filter(Boolean).join(", "),
      rule: r,
    })),
    ...asRule(p.window).map((r) => ({
      label: "Cover window",
      text: [num(r.pre_days) !== null ? `${r.pre_days} days before admission` : null, num(r.post_days) !== null ? `${r.post_days} days after discharge` : null]
        .filter(Boolean).join(", ") || "Not stated",
      rule: r,
    })),
  ];
  const cite = (r: { page: number; quote: string }): Citation => ({ doc: "policy", page: r.page, quote: r.quote, bbox: null, source: "page" });
  const chip = (r: Rule) => (
    <button type="button" className="chip mono clause-chip" onClick={() => onOpenClause(cite(r))}>
      {r.clause ? `cl. ${r.clause} · ` : ""}{citationLabel(cite(r))}
    </button>
  );

  return (
    <div className="rulebook">
      {rows.length === 0 ? <p className="muted">No rules were read from the policy.</p> : (
        <dl className="rule-list">
          {rows.map((row, i) => (
            <div key={i} className="rule-row">
              <dt>{row.label}</dt>
              <dd><span>{row.text}</span> {chip(row.rule)}</dd>
            </div>
          ))}
        </dl>
      )}
      {notVerified.length > 0 && (
        <>
          <h4 className="rule-unverified-title">Rules not verified</h4>
          <p className="muted">These were read but their quote was not found on the page, so they were not applied.</p>
          <ul className="rule-unverified">
            {notVerified.map((r, i) => (
              <li key={i}>
                <strong>{r.rule}</strong> {r.clause && <span className="mono">cl. {r.clause}</span>} <q>{r.quote}</q>{" "}
                <button type="button" className="chip mono clause-chip" onClick={() => onOpenClause(cite(r))}>policy p.{r.page}</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
