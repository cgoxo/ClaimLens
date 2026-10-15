import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Protocol

from claimlens.models import Case, CaseFile, Finding, PageInfo, now


RUNNING = {"READING", "CHECKING", "PROVING"}


def can_claim(case: Case, attempt: int) -> bool:
    """A delivery may run a case that is queued, or take over a running one from an earlier delivery."""
    return (case.status == "QUEUED" or case.status in RUNNING) and attempt > case.run_attempt


def append_file(case: Case, card_id: str, file: CaseFile) -> tuple[int, Case]:
    """Add a file to a card; a file the browser already sent (same client_id) is not added twice."""
    card = next(c for c in case.cards if c.id == card_id)
    if file.client_id:
        for i, f in enumerate(card.files):
            if f.client_id == file.client_id:
                return i, case
    card.files.append(file)
    return len(card.files) - 1, case


class Db(Protocol):
    def create_case(self, case: Case) -> None: ...
    def get_case(self, case_id: str) -> Case | None: ...
    def update_case(self, case_id: str, **fields) -> Case: ...
    def list_cases(self, owner: str) -> list[Case]: ...
    def count_cases_since(self, owner: str, since: datetime) -> int: ...
    def put_findings(self, case_id: str, findings: list[Finding]) -> None: ...
    def get_findings(self, case_id: str) -> list[Finding]: ...
    def update_finding(self, case_id: str, fid: str, **fields) -> Finding | None: ...
    def put_pages(self, case_id: str, pages: list[PageInfo]) -> None: ...
    def get_pages(self, case_id: str) -> list[PageInfo]: ...
    def get_invoice(self, key: str) -> dict | None: ...
    def claim_run(self, case_id: str, attempt: int) -> bool: ...
    def add_case_file(self, case_id: str, card_id: str, file: CaseFile) -> int: ...
    def put_invoice(self, key: str, doc: dict) -> None: ...


class LocalDb:
    """A tiny JSON-file database for local runs and tests.

    One file per document: root/cases/<id>.json, root/findings/<case>.json,
    root/pages/<case>.json, root/invoices/<key>.json. One lock serialises writes.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._lock = threading.Lock()

    def _path(self, collection: str, key: str) -> Path:
        return self.root / collection / f"{key}.json"

    def _read(self, collection: str, key: str):
        path = self._path(collection, key)
        return json.loads(path.read_text()) if path.is_file() else None

    def _write(self, collection: str, key: str, data) -> None:
        path = self._path(collection, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, default=str))
        os.replace(tmp, path)

    # cases
    def create_case(self, case: Case) -> None:
        with self._lock:
            self._write("cases", case.id, case.model_dump(mode="json"))

    def get_case(self, case_id: str) -> Case | None:
        data = self._read("cases", case_id)
        return Case.model_validate(data) if data else None

    def update_case(self, case_id: str, **fields) -> Case:
        with self._lock:
            case = self.get_case(case_id)
            if case is None:
                raise KeyError(case_id)
            case = case.model_copy(update={**fields, "updated_at": now()})
            self._write("cases", case_id, case.model_dump(mode="json"))
            return case

    def _all_cases(self) -> list[Case]:
        folder = self.root / "cases"
        if not folder.is_dir():
            return []
        return [Case.model_validate(json.loads(p.read_text())) for p in folder.glob("*.json")]

    def list_cases(self, owner: str) -> list[Case]:
        cases = [c for c in self._all_cases() if c.owner_email == owner]
        return sorted(cases, key=lambda c: c.created_at, reverse=True)

    def count_cases_since(self, owner: str, since: datetime) -> int:
        return sum(1 for c in self._all_cases() if c.owner_email == owner and c.created_at >= since)

    def claim_run(self, case_id: str, attempt: int) -> bool:
        with self._lock:
            case = self.get_case(case_id)
            if case is None or not can_claim(case, attempt):
                return False
            self._write("cases", case_id, case.model_copy(update={"run_attempt": attempt}).model_dump(mode="json"))
            return True

    def add_case_file(self, case_id: str, card_id: str, file: CaseFile) -> int:
        with self._lock:
            case = self.get_case(case_id)
            index, case = append_file(case, card_id, file)
            self._write("cases", case_id, case.model_dump(mode="json"))
            return index

    # findings
    def put_findings(self, case_id: str, findings: list[Finding]) -> None:
        with self._lock:
            self._write("findings", case_id, [f.model_dump(mode="json") for f in findings])

    def get_findings(self, case_id: str) -> list[Finding]:
        return [Finding.model_validate(f) for f in self._read("findings", case_id) or []]

    def update_finding(self, case_id: str, fid: str, **fields) -> Finding | None:
        with self._lock:
            findings = self.get_findings(case_id)
            for i, f in enumerate(findings):
                if f.id == fid:
                    findings[i] = f.model_copy(update=fields)
                    self._write("findings", case_id, [x.model_dump(mode="json") for x in findings])
                    return findings[i]
            return None

    # pages
    def put_pages(self, case_id: str, pages: list[PageInfo]) -> None:
        with self._lock:
            self._write("pages", case_id, [p.model_dump(mode="json") for p in pages])

    def get_pages(self, case_id: str) -> list[PageInfo]:
        return [PageInfo.model_validate(p) for p in self._read("pages", case_id) or []]

    # invoices
    def get_invoice(self, key: str) -> dict | None:
        return self._read("invoices", key)

    def put_invoice(self, key: str, doc: dict) -> None:
        with self._lock:
            self._write("invoices", key, doc)


class FirestoreDb:
    """Firestore (named database). cases/{id} with findings/ and pages/ subcollections; invoices/{key}.

    Owner queries use a single equality filter and sort in Python, so no composite index is needed.
    """

    def __init__(self, project: str, database: str):
        from google.cloud import firestore

        self.client = firestore.Client(project=project, database=database)

    def _case(self, case_id: str):
        return self.client.collection("cases").document(case_id)

    def create_case(self, case: Case) -> None:
        self._case(case.id).set(case.model_dump(mode="json"))

    def get_case(self, case_id: str) -> Case | None:
        snap = self._case(case_id).get()
        return Case.model_validate(snap.to_dict()) if snap.exists else None

    def update_case(self, case_id: str, **fields) -> Case:
        case = self.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        case = case.model_copy(update={**fields, "updated_at": now()})
        data = case.model_dump(mode="json")
        self._case(case_id).update({k: data[k] for k in [*fields, "updated_at"]})
        return case

    def claim_run(self, case_id: str, attempt: int) -> bool:
        from google.cloud import firestore

        ref = self._case(case_id)

        @firestore.transactional
        def claim(transaction) -> bool:
            snap = ref.get(transaction=transaction)
            if not snap.exists or not can_claim(Case.model_validate(snap.to_dict()), attempt):
                return False
            transaction.update(ref, {"run_attempt": attempt})
            return True

        return claim(self.client.transaction())

    def add_case_file(self, case_id: str, card_id: str, file: CaseFile) -> int:
        from google.cloud import firestore

        ref = self._case(case_id)

        @firestore.transactional
        def add(transaction) -> int:
            case = Case.model_validate(ref.get(transaction=transaction).to_dict())
            index, case = append_file(case, card_id, file)
            transaction.update(ref, {"cards": case.model_dump(mode="json")["cards"], "updated_at": now().isoformat()})
            return index

        return add(self.client.transaction())

    def _owned(self, owner: str) -> list[Case]:
        docs = self.client.collection("cases").where("owner_email", "==", owner).stream()
        return [Case.model_validate(d.to_dict()) for d in docs]

    def list_cases(self, owner: str) -> list[Case]:
        return sorted(self._owned(owner), key=lambda c: c.created_at, reverse=True)

    def count_cases_since(self, owner: str, since: datetime) -> int:
        return sum(1 for c in self._owned(owner) if c.created_at >= since)

    def _replace(self, collection, docs: dict[str, dict]) -> None:
        batch = self.client.batch()
        for old in collection.stream():
            batch.delete(old.reference)
        for key, data in docs.items():
            batch.set(collection.document(key), data)
        batch.commit()

    def put_findings(self, case_id: str, findings: list[Finding]) -> None:
        self._replace(self._case(case_id).collection("findings"),
                      {f.id: {**f.model_dump(mode="json"), "order": i} for i, f in enumerate(findings)})

    def get_findings(self, case_id: str) -> list[Finding]:
        docs = sorted((d.to_dict() for d in self._case(case_id).collection("findings").stream()),
                      key=lambda d: d.get("order", 0))
        return [Finding.model_validate(d) for d in docs]

    def update_finding(self, case_id: str, fid: str, **fields) -> Finding | None:
        ref = self._case(case_id).collection("findings").document(fid)
        snap = ref.get()
        if not snap.exists:
            return None
        finding = Finding.model_validate(snap.to_dict()).model_copy(update=fields)
        data = finding.model_dump(mode="json")
        ref.update({k: data[k] for k in fields})
        return finding

    def put_pages(self, case_id: str, pages: list[PageInfo]) -> None:
        # page text can be long; Firestore documents max out at 1 MB
        self._replace(self._case(case_id).collection("pages"),
                      {f"{p.doc}_{p.page}": {**p.model_dump(mode="json"), "text": p.text[:200_000]} for p in pages})

    def get_pages(self, case_id: str) -> list[PageInfo]:
        pages = [PageInfo.model_validate(d.to_dict()) for d in self._case(case_id).collection("pages").stream()]
        return sorted(pages, key=lambda p: (p.doc != "claim", p.page))

    def get_invoice(self, key: str) -> dict | None:
        snap = self.client.collection("invoices").document(key).get()
        return snap.to_dict() if snap.exists else None

    def put_invoice(self, key: str, doc: dict) -> None:
        self.client.collection("invoices").document(key).set(doc)
