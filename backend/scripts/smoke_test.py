"""Upload the samples to a running ClaimLens and check the result. Exit 0 on success."""

import argparse
import sys
import time
from pathlib import Path

import httpx

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
EXPECTED = {"font_outlier", "hidden_text", "editing_tool", "sum_mismatch", "inpatient_outside_stay",
            "name_mismatch", "duplicate_invoice", "waiting_period", "room_rent_limit"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--dev-user")
    who.add_argument("--token")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()
    headers = {"X-Dev-User": args.dev_user} if args.dev_user else {"Authorization": f"Bearer {args.token}"}

    with httpx.Client(base_url=args.base_url, headers=headers, timeout=60) as http:
        print("health:", http.get("/health").json())
        cards = [{"id": "claim-form", "role": "claim_form"}, {"id": "policy", "role": "policy"}]
        r = http.post("/api/cases", json={"cards": cards})
        r.raise_for_status()
        case_id = r.json()["case_id"]
        for card_id, name in (("claim-form", "claim.pdf"), ("policy", "policy.pdf")):
            http.post(f"/api/cases/{case_id}/files", data={"card_id": card_id},
                      files={"file": (name, (SAMPLES / name).read_bytes(), "application/pdf")}).raise_for_status()
        http.post(f"/api/cases/{case_id}/submit").raise_for_status()
        print("case:", case_id)
        deadline = time.time() + args.timeout
        case = {"status": "QUEUED"}
        while time.time() < deadline:
            r = http.get(f"/api/cases/{case_id}")
            if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
                print(f"retrying after HTTP {r.status_code}: {r.text[:120]!r}")
                time.sleep(2)
                continue
            case = r.json()
            print("status:", case["status"])
            if case["status"] in ("READY", "FAILED"):
                break
            time.sleep(2)
        if case["status"] != "READY":
            print("FAILED:", case.get("step"), case.get("error"))
            return 1
        codes = {f["code"] for f in case["findings"]}
        print(f"score {case['score']} risk {case['risk']} payable {case['payable']}")
        for f in case["findings"]:
            c = f["citations"][0]
            print(f"  {f['severity']:<9} {f['title']}  ({c['doc']} p.{c['page']})")
        missing = EXPECTED - codes
        if missing:
            print("MISSING:", sorted(missing))
            return 1
        print("OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
