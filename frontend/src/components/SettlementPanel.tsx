import type { ReactNode } from "react";
import type { Citation, Deduction, Settlement } from "../api/types";
import { citationLabel } from "../lib/findings";
import { money } from "../lib/format";

interface Props {
  settlement: Settlement;
  onOpenClause(c: Citation): void;
}

export default function SettlementPanel({ settlement: s, onOpenClause }: Props) {
  const chip = (d: Deduction) => d.rule && (
    <button type="button" className="chip mono clause-chip" onClick={() => onOpenClause(d.rule!)}>{citationLabel(d.rule)}</button>
  );
  // a deduction under the item that carries it, or a total row of its own
  const deductionRow = (d: Deduction, key: string, label?: ReactNode) => (
    <tr key={key} className="settle-deduction">
      <td colSpan={3}>{label && <strong>{label}: </strong>}{d.reason} {chip(d)}</td>
      <td className="num mono">−{money(d.amount)}</td>
      <td />
    </tr>
  );

  const admissible = s.lines.reduce((sum, l) => sum + l.payable, 0) - s.claim_level.reduce((sum, d) => sum + d.amount, 0);
  const capped = admissible - s.subtotal;

  return (
    <div className="settlement">
      <table className="settle-table">
        <thead>
          <tr><th>Item</th><th>Type</th><th className="num">Claimed</th><th className="num">Deducted</th><th className="num">Payable</th></tr>
        </thead>
        <tbody>
          {s.lines.flatMap((l) => [
            <tr key={`l-${l.bill}-${l.line}`} className="settle-line">
              <td>{l.desc}</td>
              <td className="muted">{l.category}</td>
              <td className="num mono">{money(l.claimed)}</td>
              <td className="num mono">{money(l.claimed - l.payable)}</td>
              <td className="num mono">{money(l.payable)}</td>
            </tr>,
            ...l.deductions.map((d, i) => deductionRow(d, `d-${l.bill}-${l.line}-${i}`)),
          ])}
          {s.whole_claim && deductionRow(s.whole_claim, "whole", "Whole claim")}
          {s.claim_level.map((d, i) => deductionRow(d, `c-${i}`, "Claim level"))}
          {capped > 0.5 && (
            <tr className="settle-deduction">
              <td colSpan={3}>Capped at the claimed amount</td>
              <td className="num mono">−{money(capped)}</td>
              <td />
            </tr>
          )}
          <tr className="settle-total">
            <td colSpan={4}>Subtotal</td>
            <td className="num mono">{money(s.subtotal)}</td>
          </tr>
          {s.sub_limit && deductionRow(s.sub_limit, "sub", "Sub-limit")}
          {s.deductible && deductionRow(s.deductible, "ded", "Deductible")}
          {s.co_pay && deductionRow(s.co_pay, "copay", "Co-pay")}
          {s.si_cap && deductionRow(s.si_cap, "si", "Sum insured cap")}
          <tr className="settle-total settle-final">
            <th scope="row" colSpan={4}>Payable</th>
            <td className="num mono">{money(s.payable)}</td>
          </tr>
        </tbody>
      </table>
      {s.notes.length > 0 && (
        <ul className="settle-notes">{s.notes.map((n, i) => <li key={i}>{n.text}</li>)}</ul>
      )}
    </div>
  );
}
