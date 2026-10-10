"""Seed the 'past claims' history so the sample claim's invoice shows up as a duplicate.

Uses the same settings as the app (.env / env vars), so it writes to the local DB or Firestore.
"""

from claimlens.deps import build_deps
from claimlens.settings import Settings

ROWS = {"INVSEH20260412": {"invoice_no": "INV-SEH-2026-0412", "amount": 45500, "case_id": "CLM-1043"}}

if __name__ == "__main__":
    settings = Settings()
    db = build_deps(settings.model_copy(update={"ai": "fake", "ocr": "off"})).db
    for key, row in ROWS.items():
        db.put_invoice(key, row)
    print(f"seeded {len(ROWS)} invoice(s) into {settings.db} db")
