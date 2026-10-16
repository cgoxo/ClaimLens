"""Run a scenario through ClaimLens: in-process, through the real upload API and pipeline."""

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from claimlens.deps import build_deps
from claimlens.main import create_app
from claimlens.pipeline.checks.duplicate import invoice_key
from claimlens.settings import Settings
from eval.scenarios.fake_ai import TruthAi
from eval.scenarios.render import render

USER = {"X-Dev-User": "eval@claimlens.test"}


@dataclass
class CaseResult:
    status: str | None
    codes: Counter
    band: str | None
    payable: float | None
    error: str | None
    seconds: float
    case_id: str | None
    recommendation: str | None = None


class LocalTarget:
    """A fresh app, storage and database per case (so invoices from one scenario never leak into the next).
    `ai` None means the offline stand-in (TruthAi); otherwise a factory for the real AI."""

    def __init__(self, root: Path, ai_factory=None, ocr=None):
        self.root, self.ai_factory, self.ocr, self.n = Path(root), ai_factory, ocr, 0

    def run(self, recipe, forgeries: list[str], fmt: str, truth) -> CaseResult:
        self.n += 1
        settings = Settings(_env_file=None, data_dir=self.root / f"case{self.n}", ai="fake", jobs="inline",
                            daily_case_limit=10**6)
        deps = build_deps(settings)
        deps.ai = self.ai_factory() if self.ai_factory else TruthAi(truth)
        if self.ocr is not None:
            deps.ocr = self.ocr
        if "reused_invoice" in forgeries:  # an earlier claim already used this invoice
            deps.db.put_invoice(invoice_key(recipe.invoice), {"invoice_no": recipe.invoice, "case_id": "EARLIER"})
        client = TestClient(create_app(settings, deps))
        started = time.time()
        r = client.post("/api/cases", json={"cards": [{"id": "claim", "role": "claim"},
                                                       {"id": "policy", "role": "policy"}]}, headers=USER)
        if r.status_code != 201:
            return CaseResult(None, Counter(), None, None, f"create: {r.text}", 0, None)
        case_id = r.json()["case_id"]
        for card, name, data in render(recipe, forgeries, fmt):
            r = client.post(f"/api/cases/{case_id}/files", data={"card_id": card},
                            files={"file": (name, data, "application/octet-stream")}, headers=USER)
            if r.status_code != 201:
                return CaseResult(None, Counter(), None, None, f"upload {name}: {r.text}", 0, case_id)
        r = client.post(f"/api/cases/{case_id}/submit", headers=USER)
        if r.status_code != 200:
            return CaseResult(None, Counter(), None, None, f"submit: {r.text}", 0, case_id)
        case = client.get(f"/api/cases/{case_id}", headers=USER).json()
        advice = ((case.get("current") or {}).get("recommendation") or {}).get("action")
        return CaseResult(case["status"], Counter(f["code"] for f in case["findings"]), case["risk"],
                          case["payable"], case["error"] if case["status"] == "FAILED" else None,
                          time.time() - started, case_id, advice)
