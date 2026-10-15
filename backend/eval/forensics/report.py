"""Write the forensics measurement report (markdown) from results.jsonl.

python -m eval.forensics.report
"""

import json
import statistics
from datetime import date as today
from pathlib import Path

from eval.forensics.score import SET, fused, keep, metrics

DOCS = Path(__file__).resolve().parents[3] / "docs" / "eval"
FORGERIES = ("G", "G2", "G3", "P", "C")
USD_INR = 84
# per-second rates from the Cloud Billing catalogue (Cloud Run, instance-based)
RATE_CPU_JOB = 4 * 0.000018 + 8 * 0.000002  # asia-south1, 4 vCPU 8 GiB
RATE_GPU_JOB = 0.00022404 + 4 * 0.0000216 + 16 * 0.0000024  # asia-southeast1, L4 + 4 vCPU 16 GiB
RATE_API = 0.000018 + 1 * 0.000002  # the existing service's own CPU, per vCPU-second


def _fmt(v, pct=False):
    if v is None:
        return "–"
    return f"{100 * v:.0f}%" if pct else f"{v:.2f}"


def render(rows: list[dict], date: str | None = None) -> str:
    detectors = sorted({r["detector"] for r in rows})
    candidates = [d for d in detectors if not d.startswith("fused")]
    rows = rows + fused(rows, candidates)
    detectors = sorted({r["detector"] for r in rows})
    lines = [f"# Pixel forensics: measurement report ({date or today.today().isoformat()})", "",
             "Field-level scores on our own forged test set (fictional bills, phone-like photos). Thresholds are "
             "fixed on half A of the bills at 5% false positives on genuine numbers; everything below is half B. "
             "**Keep rule:** AUC ≥ 0.70 on G or G2, and ≤ 5% false positives on every genuine condition.", "",
             "Forgery kinds:",
             "- **G:** a Gemini image edit pasted back into the field;",
             "- **G2:** G, then shared at q70;",
             "- **G3:** total and item edited together (the arithmetic still holds);",
             "- **P:** retyped;",
             "- **C:** a copied digit.", "",
             "## Verdict", "",
             "| Detector | AUC (G) | AUC (G2) | Catches G at 5% FP | Worst genuine FP | No opinion | ₹/case | Verdict |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    details = []
    for d in detectors:
        g, g2 = metrics(rows, d, ("G",)), metrics(rows, d, ("G2",))
        best = max((g, g2), key=lambda m: m["auc"] or 0)
        worst = max((v for v in best["fpr_by_control"].values() if v is not None), default=None)
        seconds = [r["seconds"] for r in rows if r["detector"] == d and r.get("seconds") is not None]
        median = statistics.median(seconds) if seconds else None
        rate = RATE_GPU_JOB if d == "catnet" else RATE_API
        cost = f"₹{median * rate * USD_INR * 10:.2f}" if median is not None else "–"  # ~10 photo pages per case
        verdict = "KEEP" if keep(best) else "DROP"
        lines.append(f"| {d} | {_fmt(g['auc'])} | {_fmt(g2['auc'])} | {_fmt(g['tpr_at_5fpr'], True)} | "
                     f"{_fmt(worst, True)} | {g['n_no_opinion']} | {cost} | **{verdict}** |")
        details.append(f"### {d}")
        details.append("")
        details.append("| Kind | AUC | Caught at 5% FP | Positives | Negatives |")
        details.append("| --- | --- | --- | --- | --- |")
        for kind in FORGERIES:
            m = metrics(rows, d, (kind,))
            details.append(f"| {kind} | {_fmt(m['auc'])} | {_fmt(m['tpr_at_5fpr'], True)} | {m['n_pos']} | {m['n_neg']} |")
        details.append("")
        details.append("False positives by genuine condition: " + ", ".join(
            f"{k} {_fmt(v, True)}" for k, v in best["fpr_by_control"].items()) + ".")
        details.append("")
    lines += ["", "## Per detector", "", *details,
              "## Known limits", "",
              "- A page that is entirely AI-generated, or a forgery re-photographed from a screen, leaves no "
              "local trace to find.",
              "- PNG uploads carry no JPEG history: ela, dq and catnet have no opinion on them.",
              "- Copy-move only judges near-lossless images (PNG, or JPEG q ≥ 93).",
              "- The set is our own fictional bills: real phone photos vary more (lighting, angle, paper).", "",
              "## Cost basis", "",
              f"- ₹/case assumes 10 photographed pages per case at ₹{USD_INR}/$.",
              f"- catnet: L4 GPU job in asia-southeast1, ${RATE_GPU_JOB:.7f}/s (or a CPU job in asia-south1, "
              f"${RATE_CPU_JOB:.7f}/s).",
              f"- Every other detector runs in the existing service, ${RATE_API:.7f}/vCPU-s.",
              "- gemini_closeup also costs about ₹0.3 per case in Gemini tokens."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    rows = [json.loads(l) for l in (SET / "results.jsonl").read_text().splitlines()]
    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / f"forensics-{today.today().isoformat()}.md"
    out.write_text(render(rows))
    print(out)
