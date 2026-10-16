"""The scenario report: how ClaimLens did case by case, per finding, and on risk, payable and rejections."""

import json
from collections import Counter
from datetime import date as today
from pathlib import Path

BANDS = ["low", "review", "high"]
ACTIONS = ["investigate", "query", "not_payable", "approve_part", "approve"]
RULES = ["waiting_period", "room_rent_limit", "icu_limit", "non_payable_items", "bill_outside_cover_window"]


def code_table(rows: list[dict]) -> dict[str, dict]:
    totals: dict[str, Counter] = {}
    for r in rows:
        exp, got = Counter(r["expected_codes"]), Counter(r["found_codes"])
        for code in set(exp) | set(got):
            t = totals.setdefault(code, Counter())
            t["tp"] += min(exp[code], got[code])
            t["fp"] += max(0, got[code] - exp[code])
            t["fn"] += max(0, exp[code] - got[code])
    out = {}
    for code, t in sorted(totals.items()):
        p = t["tp"] / (t["tp"] + t["fp"]) if t["tp"] + t["fp"] else None
        rc = t["tp"] / (t["tp"] + t["fn"]) if t["tp"] + t["fn"] else None
        out[code] = {"tp": t["tp"], "fp": t["fp"], "fn": t["fn"], "precision": p, "recall": rc}
    return out


def band_matrix(rows: list[dict]) -> dict[str, Counter]:
    m = {b: Counter() for b in BANDS + ["none"]}
    for r in rows:
        m[r["band_expected"] or "none"][r["band_found"] or "none"] += 1
    return m


def action_matrix(rows: list[dict]) -> dict[str, Counter]:
    """Expected recommendation (rows) against the one found (columns), for the cases that have one."""
    m = {a: Counter() for a in ACTIONS}
    for r in rows:
        if r.get("recommendation_expected") is not None:
            m[r["recommendation_expected"]][r.get("recommendation_found") or "none"] += 1
    return m


def rule_table(rows: list[dict]) -> dict[str, dict]:
    """Per policy rule: cases where truth expects it, and how many of those ClaimLens found and proved
    (a finding is stored only after its quote is proved on the policy page)."""
    out = {}
    for code in RULES:
        wanted = [r for r in rows if r["expected_codes"].get(code)]
        out[code] = {"expected": len(wanted), "proved": sum(1 for r in wanted if r["found_codes"].get(code))}
    return out


def passed(r: dict) -> bool:
    """Right status, no missing codes, no extra codes other than low ones."""
    if r["error"] or r["status_expected"] != r["status_found"]:
        return False
    exp, got = Counter(r["expected_codes"]), Counter(r["found_codes"])
    return not (exp - got) and not any(c for c in (got - exp) if c != "unreadable_file")


def worst(rows: list[dict], n: int = 10) -> list[dict]:
    def badness(r):
        exp, got = Counter(r["expected_codes"]), Counter(r["found_codes"])
        return (bool(r["error"]) or r["status_expected"] != r["status_found"], sum((exp - got).values()),
                sum((got - exp).values()))
    return sorted([r for r in rows if not passed(r)], key=badness, reverse=True)[:n]


def _pct(v) -> str:
    return "n/a" if v is None else f"{100 * v:.0f}%"


def render(rows: list[dict], target: str, date: str | None = None) -> str:
    n = len(rows)
    ok = sum(passed(r) for r in rows)
    pay = [r for r in rows if r["payable_expected"] is not None]
    pay_ok = sum(1 for r in pay if r["payable_found"] is not None and abs(r["payable_found"] - r["payable_expected"]) <= 1)
    rej = [r for r in rows if r["status_expected"] == "REJECTED" or r["status_found"] == "REJECTED"]
    rej_ok = sum(1 for r in rej if r["status_expected"] == r["status_found"])
    lines = [f"# Scenario suite: {target} ({date or today.today().isoformat()})", "",
             f"{n} generated claims (clean, coverage-only, single and combined forgeries, rejections), uploaded "
             "through the real API and analysed by the real pipeline.", "",
             f"## Case pass rate: {ok}/{n} ({_pct(ok / n if n else None)})", "",
             "A case passes with the right status, no missing finding, and no extra finding other than low notes.", "",
             "## Per finding", "", "| Code | TP | FP | FN | Precision | Recall |", "| --- | --- | --- | --- | --- | --- |"]
    for code, t in code_table(rows).items():
        lines.append(f"| {code} | {t['tp']} | {t['fp']} | {t['fn']} | {_pct(t['precision'])} | {_pct(t['recall'])} |")
    m = band_matrix(rows)
    lines += ["", "## Risk band (rows: expected, columns: found)", "", "| | " + " | ".join(BANDS + ["none"]) + " |",
              "| --- " * 5 + "|"]
    for b in BANDS + ["none"]:
        lines.append(f"| **{b}** | " + " | ".join(str(m[b][c]) for c in BANDS + ["none"]) + " |")
    lines += ["", f"## Payable: {pay_ok}/{len(pay)} within ₹1", ""]
    advised = [r for r in rows if r.get("recommendation_expected") is not None]
    advice_ok = sum(1 for r in advised if r["recommendation_expected"] == r.get("recommendation_found"))
    am = action_matrix(rows)
    lines += [f"## Recommendation: {advice_ok}/{len(advised)} correct", "",
              "| (rows: expected, columns: found) | " + " | ".join(ACTIONS + ["none"]) + " |", "| --- " * 7 + "|"]
    for a in ACTIONS:
        lines.append(f"| **{a}** | " + " | ".join(str(am[a][c]) for c in ACTIONS + ["none"]) + " |")
    lines += ["", "## Policy rules found and proved", "", "| Rule | Cases expected | Found and proved |", "| --- | --- | --- |"]
    for code, t in rule_table(rows).items():
        lines.append(f"| {code} | {t['expected']} | {t['proved']} |")
    lines += ["",
              f"## Rejections: {rej_ok}/{len(rej)} right", "", "## By format", "",
              "| Format | Cases | Passed |", "| --- | --- | --- |"]
    for fmt in sorted({r["fmt"] for r in rows}):
        sub = [r for r in rows if r["fmt"] == fmt]
        lines.append(f"| {fmt} | {len(sub)} | {sum(passed(r) for r in sub)} |")
    lines += ["", "## Worst cases", ""]
    for r in worst(rows):
        exp, got = Counter(r["expected_codes"]), Counter(r["found_codes"])
        lines.append(f"- seed {r['seed']} {r['fmt']} {r['forgeries'] or ['clean']}: status {r['status_expected']}→"
                     f"{r['status_found']}; missing {dict(exp - got)}; extra {dict(got - exp)}"
                     f"{'; error ' + r['error'][:120] if r['error'] else ''} (case {r['case_id']})")
    seconds = sorted(r["seconds"] for r in rows)
    lines += ["", f"Median time per case: {seconds[len(seconds) // 2]:.1f} s." if seconds else ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1])
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    out = Path(__file__).resolve().parents[3] / "docs" / "eval" / f"scenarios-live-{today.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows, target="live"))
    print(out)
