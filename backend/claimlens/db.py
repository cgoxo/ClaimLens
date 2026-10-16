import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Protocol

from claimlens.models import Case, CaseFile, ChatMessage, ChatThread, Finding, PageInfo, Proposal, now


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


def _version_doc(number: int, finding: Finding, action: str, by: str, note: str) -> dict:
    return {"version": number, "action": action, "by": by, "note": note, "at": now().isoformat(),
            "finding": finding.model_dump(mode="json")}


class Db(Protocol):
    def create_case(self, case: Case) -> None: ...
    def get_case(self, case_id: str) -> Case | None: ...
    def update_case(self, case_id: str, **fields) -> Case: ...
    def list_cases(self, owner: str) -> list[Case]: ...
    def count_cases_since(self, owner: str, since: datetime) -> int: ...
    def put_findings(self, case_id: str, findings: list[Finding]) -> None: ...
    def get_findings(self, case_id: str) -> list[Finding]: ...
    def update_finding(self, case_id: str, fid: str, **fields) -> Finding | None: ...
    def add_finding_version(self, case_id: str, fid: str, finding: Finding, action: str, by: str,
                            note: str) -> int: ...
    def get_finding_versions(self, case_id: str, fid: str) -> list[dict]: ...
    def put_pages(self, case_id: str, pages: list[PageInfo]) -> None: ...
    def get_pages(self, case_id: str) -> list[PageInfo]: ...
    def get_invoice(self, key: str) -> dict | None: ...
    def claim_run(self, case_id: str, attempt: int) -> bool: ...
    def add_case_file(self, case_id: str, card_id: str, file: CaseFile) -> int: ...
    def put_invoice(self, key: str, doc: dict) -> None: ...
    def active_thread(self, case_id: str) -> ChatThread | None: ...
    def create_thread(self, case_id: str, thread: ChatThread) -> None: ...
    def close_thread(self, case_id: str, thread_id: str, summary: str) -> None: ...
    def list_threads(self, case_id: str) -> list[ChatThread]: ...
    def add_message(self, case_id: str, thread_id: str, msg: ChatMessage) -> None: ...
    def get_messages(self, case_id: str, thread_id: str) -> list[ChatMessage]: ...
    def update_proposal(self, case_id: str, thread_id: str, message_id: str, proposal: Proposal) -> None: ...
    def count_messages_since(self, owner: str, since: datetime) -> int: ...


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

    def add_finding_version(self, case_id: str, fid: str, finding: Finding, action: str, by: str,
                            note: str) -> int:
        with self._lock:
            versions = self._read("finding_versions", case_id) or {}
            rows = versions.setdefault(fid, [])
            number = max((v["version"] for v in rows), default=0) + 1
            rows.append(_version_doc(number, finding, action, by, note))
            self._write("finding_versions", case_id, versions)
            return number

    def get_finding_versions(self, case_id: str, fid: str) -> list[dict]:
        return sorted((self._read("finding_versions", case_id) or {}).get(fid, []), key=lambda v: v["version"])

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

    # chat: root/chats/<case>.json holds {thread_id: {"thread": ..., "messages": [...]}}
    def active_thread(self, case_id: str) -> ChatThread | None:
        active = [t for t in self.list_threads(case_id) if t.status == "active"]
        return active[0] if active else None

    def create_thread(self, case_id: str, thread: ChatThread) -> None:
        with self._lock:
            chats = self._read("chats", case_id) or {}
            chats[thread.id] = {"thread": thread.model_dump(mode="json"), "messages": []}
            self._write("chats", case_id, chats)

    def close_thread(self, case_id: str, thread_id: str, summary: str) -> None:
        with self._lock:
            chats = self._read("chats", case_id) or {}
            chats[thread_id]["thread"].update(status="closed", summary=summary)
            self._write("chats", case_id, chats)

    def list_threads(self, case_id: str) -> list[ChatThread]:
        threads = [ChatThread.model_validate(c["thread"]) for c in (self._read("chats", case_id) or {}).values()]
        return sorted(threads, key=lambda t: t.created_at, reverse=True)

    def add_message(self, case_id: str, thread_id: str, msg: ChatMessage) -> None:
        with self._lock:
            chats = self._read("chats", case_id) or {}
            chats[thread_id]["messages"].append(msg.model_dump(mode="json"))
            self._write("chats", case_id, chats)

    def get_messages(self, case_id: str, thread_id: str) -> list[ChatMessage]:
        rows = (self._read("chats", case_id) or {}).get(thread_id, {}).get("messages", [])
        return sorted((ChatMessage.model_validate(m) for m in rows), key=lambda m: m.created_at)

    def update_proposal(self, case_id: str, thread_id: str, message_id: str, proposal: Proposal) -> None:
        with self._lock:
            chats = self._read("chats", case_id) or {}
            for m in chats[thread_id]["messages"]:
                if m["id"] == message_id:
                    m["proposals"] = [proposal.model_dump(mode="json") if p["id"] == proposal.id else p
                                      for p in m["proposals"]]
            self._write("chats", case_id, chats)

    def count_messages_since(self, owner: str, since: datetime) -> int:
        folder = self.root / "chats"
        if not folder.is_dir():
            return 0
        count = 0
        for path in folder.glob("*.json"):
            for chat in json.loads(path.read_text()).values():
                for m in chat["messages"]:
                    msg = ChatMessage.model_validate(m)
                    count += msg.role == "reviewer" and msg.by == owner and msg.created_at >= since
        return count


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

    def add_finding_version(self, case_id: str, fid: str, finding: Finding, action: str, by: str,
                            note: str) -> int:
        from google.cloud import firestore

        col = self._case(case_id).collection("finding_versions")
        query = col.where("fid", "==", fid)

        @firestore.transactional
        def add(transaction) -> int:
            numbers = [d.to_dict()["version"] for d in query.stream(transaction=transaction)]
            number = max(numbers, default=0) + 1
            transaction.set(col.document(f"{fid}-{number}"),
                            {**_version_doc(number, finding, action, by, note), "fid": fid})
            return number

        return add(self.client.transaction())

    def get_finding_versions(self, case_id: str, fid: str) -> list[dict]:
        docs = (d.to_dict() for d in self._case(case_id).collection("finding_versions").where("fid", "==", fid).stream())
        return sorted(({k: v for k, v in d.items() if k != "fid"} for d in docs), key=lambda v: v["version"])

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

    # chat: cases/{id}/chats/{thread_id} with a messages/{message_id} subcollection
    def _chats(self, case_id: str):
        return self._case(case_id).collection("chats")

    def active_thread(self, case_id: str) -> ChatThread | None:
        docs = self._chats(case_id).where("status", "==", "active").stream()
        threads = sorted((ChatThread.model_validate(d.to_dict()) for d in docs), key=lambda t: t.created_at,
                         reverse=True)
        return threads[0] if threads else None

    def create_thread(self, case_id: str, thread: ChatThread) -> None:
        self._chats(case_id).document(thread.id).set(thread.model_dump(mode="json"))

    def close_thread(self, case_id: str, thread_id: str, summary: str) -> None:
        self._chats(case_id).document(thread_id).update({"status": "closed", "summary": summary})

    def list_threads(self, case_id: str) -> list[ChatThread]:
        threads = [ChatThread.model_validate(d.to_dict()) for d in self._chats(case_id).stream()]
        return sorted(threads, key=lambda t: t.created_at, reverse=True)

    def add_message(self, case_id: str, thread_id: str, msg: ChatMessage) -> None:
        # created_at is stored as a real timestamp so count_messages_since can compare it in the query
        data = {**msg.model_dump(mode="json"), "created_at": msg.created_at}
        self._chats(case_id).document(thread_id).collection("messages").document(msg.id).set(data)

    def get_messages(self, case_id: str, thread_id: str) -> list[ChatMessage]:
        docs = self._chats(case_id).document(thread_id).collection("messages").stream()
        return sorted((ChatMessage.model_validate(d.to_dict()) for d in docs), key=lambda m: m.created_at)

    def update_proposal(self, case_id: str, thread_id: str, message_id: str, proposal: Proposal) -> None:
        from google.cloud import firestore

        ref = self._chats(case_id).document(thread_id).collection("messages").document(message_id)

        @firestore.transactional
        def update(transaction) -> None:
            msg = ChatMessage.model_validate(ref.get(transaction=transaction).to_dict())
            proposals = [proposal if p.id == proposal.id else p for p in msg.proposals]
            transaction.update(ref, {"proposals": [p.model_dump(mode="json") for p in proposals]})

        update(self.client.transaction())

    def count_messages_since(self, owner: str, since: datetime) -> int:
        # collection-group query over every case's messages; needs a composite index on (by, role, created_at)
        docs = (self.client.collection_group("messages")
                .where("by", "==", owner).where("role", "==", "reviewer").where("created_at", ">=", since).stream())
        return sum(1 for _ in docs)
