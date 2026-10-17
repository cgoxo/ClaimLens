"""Live chat smoke: the sample case through the API with the fake pipeline AI, chat answered by real Gemini.

Run: PYTHONPATH=. python -m eval.chat_smoke   (needs Vertex credentials)
Writes docs/eval/chat-smoke-<date>.md at the repo root.
"""
import json
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from claimlens.chat.model import VertexChat
from claimlens.deps import build_deps
from claimlens.main import create_app
from claimlens.settings import Settings
from tests.conftest import SAMPLES, upload_case

H = {"X-Dev-User": "smoke@x.com"}
QUESTIONS = [
    "What is the claimed amount and where is it?",
    "Why was money deducted for the room?",
    "Does the bill total match its items?",
    "Is this number right?",  # with a selection on the bill total
    "Dismiss the name mismatch, it's a typo",
]


def total_box() -> dict:
    """The bill total on the sample claim, found with PyMuPDF."""
    doc = pymupdf.open(SAMPLES / "claim.pdf")
    for n, page in enumerate(doc, 1):
        for r in page.search_for("45,500"):
            return {"doc": "claim", "page": n, "bbox": [r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2]}
    raise SystemExit("bill total not found")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, data_dir=tmp, ai="fake", jobs="inline", daily_case_limit=1000)
    app = create_app(settings, build_deps(settings))
    client = TestClient(app)
    r = upload_case(client, H)
    assert r.status_code < 300, r.text
    cid = r.json()["case_id"]
    case = client.get(f"/api/cases/{cid}", headers=H).json()
    assert case["status"] == "READY", case["status"]
    app.state.deps.chat_ai = VertexChat("social-pulse-510513", "global", "gemini-2.5-flash")
    box = total_box()

    rows, checks = [], []
    for i, q in enumerate(QUESTIONS, 1):
        body = {"text": q, **({"selection": box} if i == 4 else {})}
        t0 = time.time()
        resp = client.post(f"/api/cases/{cid}/chat/messages", json=body, headers=H)
        secs = time.time() - t0
        if resp.status_code != 200:
            print(f"Q{i} failed: {resp.status_code} {resp.text}")
            return 1
        rows.append((q, resp.json(), secs))
        print(f"Q{i} {secs:.1f}s ok", flush=True)

    for i, (q, m, _) in enumerate(rows, 1):
        ok = bool(m["citations"]) or not m["verified"]
        checks.append((f"Q{i} has a proved citation or is marked unverified", ok))

    q5 = rows[4][1]
    dismiss = [p for p in q5["proposals"] if p["type"] == "review_finding" and p["action"] == "dismiss"]
    checks.append(("Q5 yields a review_finding dismiss proposal", bool(dismiss)))
    apply_dump = "n/a"
    if dismiss:
        p = dismiss[0]
        before = client.get(f"/api/cases/{cid}", headers=H).json()
        f_before = next((f for f in before["findings"] if f["id"] == p["finding_id"]), {})
        checks.append(("Q5 proposal not applied before Apply (finding unreviewed, proposal pending)",
                       not f_before.get("review") and p["status"] == "pending"))
        ap = client.post(f"/api/cases/{cid}/chat/proposals/{p['id']}/apply", headers=H)
        applied = ap.status_code == 200 and ap.json()["proposal"]["status"] == "applied"
        checks.append(("Apply succeeds", applied))
        cur = ap.json().get("current") if ap.status_code == 200 else None
        after = client.get(f"/api/cases/{cid}", headers=H).json()
        f_after = next((f for f in after["findings"] if f["id"] == p["finding_id"]), {})
        checks.append(("Apply changes `current` (outcome returned, finding now reviewed)",
                       bool(cur) and bool(f_after.get("review"))))
        apply_dump = json.dumps(cur, indent=1)[:1500] if cur else f"none ({ap.status_code} {ap.text[:300]})"

    out = [f"# Chat smoke test, live ({date.today()})", "",
           "Sample case through the API (pipeline AI: fake, jobs inline), chat answered by real Gemini "
           "(`gemini-2.5-flash` via Vertex, project `social-pulse-510513`).", "", "## Checks", ""]
    out += [f"- {'PASS' if ok else 'FAIL'}: {name}" for name, ok in checks]
    out += ["", f"Selection for question 4: `{json.dumps(box)}`", "", "## Questions", ""]
    for i, (q, m, secs) in enumerate(rows, 1):
        out += [f"### {i}. {q}", "", f"- Seconds: {secs:.1f}", f"- Verified: {m['verified']}",
                f"- Answer: {m['text']}",
                f"- Citations kept ({len(m['citations'])}): " + "; ".join(
                    f"{c['doc']} p{c['page']} \"{c['quote']}\"" for c in m["citations"]),
                f"- Notes: {m['notes']}",
                f"- Tool calls: {[t.get('name') for t in m['tool_calls']]}",
                "- Proposals: " + json.dumps(m["proposals"]), ""]
    out += ["## Apply result for question 5", "", "```", apply_dump, "```", ""]
    path = Path(__file__).resolve().parents[2] / "docs" / "eval" / f"chat-smoke-{date.today()}.md"
    path.write_text("\n".join(out))
    print(path)
    for name, ok in checks:
        print("PASS" if ok else "FAIL", name)
    return 0 if all(ok for _, ok in checks) else 2


if __name__ == "__main__":
    sys.exit(main())
