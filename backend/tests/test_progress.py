from datetime import timedelta

from claimlens.models import Case, now
from claimlens.ocr import NoOcr
from claimlens.pipeline.read import read_document
from claimlens.pipeline.run import Progress, run_pipeline
from claimlens.storage import LocalStorage
from tests.conftest import SAMPLES
from tests.test_api import A, _client
from tests.test_pipeline import _deps, _new_case


class RecordingDb:
    def __init__(self):
        self.writes = []

    def update_case(self, case_id, **fields):
        self.writes.append(fields["progress"])


def test_throttle():
    times = iter([0.0, 0.2, 0.4, 1.5, 1.6])
    db = RecordingDb()
    p = Progress(db, "c1", clock=lambda: next(times))
    p.step("READING", "start", total=7)
    p.tick("a", 1)
    p.tick("b", 2)
    p.tick("c", 3)
    assert [w["label"] for w in db.writes] == ["start", "c"]
    p.tick("d", 4, force=True)
    assert db.writes[-1] == {"step": "READING", "done": 4, "total": 7, "label": "d"}


def test_on_page_called_per_page(tmp_path):
    calls = []
    read_document("claim", (SAMPLES / "claim.pdf").read_bytes(), "claim.pdf", "c1",
                  LocalStorage(tmp_path), NoOcr(), on_page=lambda *a: calls.append(a))
    assert calls == [("claim", n, "digital") for n in range(1, 5)]


def _recorded(deps):
    seen, original = [], deps.db.update_case

    def update_case(case_id, **fields):
        if fields.get("progress"):
            seen.append(fields["progress"]["label"])
        return original(case_id, **fields)

    deps.db.update_case = update_case
    return seen


def test_progress_labels_and_cleared(tmp_path):
    deps = _deps(tmp_path)
    labels = _recorded(deps)
    run_pipeline(_new_case(deps), deps)
    for label in ["Reading claim.pdf, page 1 (1 of 7)", "Reading policy.pdf, page 3 (7 of 7)", "Extracting facts with Gemini",
                  "Checking: tamper", "Checking coverage with Gemini", "Proving findings"]:
        assert label in labels
    case = deps.db.get_case("c1")
    assert case.status == "READY"
    assert case.progress is None and case.finished_at is not None


def test_failed_mid_read_clears_progress(tmp_path):
    deps = _deps(tmp_path)
    case_id = _new_case(deps)
    get = deps.storage.get
    deps.storage.get = lambda key: (_ for _ in ()).throw(RuntimeError("disk")) if "policy" in key else get(key)
    run_pipeline(case_id, deps)
    case = deps.db.get_case("c1")
    assert case.status == "FAILED"
    assert case.progress is None and case.finished_at is not None


def test_stale_sets_finished_at(settings):
    client = _client(settings)
    db = client.app.state.deps.db
    old = now() - timedelta(minutes=20)
    db.create_case(Case(id="s1", owner_email="a@x.com", status="READING", created_at=old, updated_at=old))
    body = client.get("/api/cases/s1", headers=A).json()
    assert body["status"] == "FAILED" and body["finished_at"] is not None


def test_stale_run_expires_in_the_list_too(settings):
    client = _client(settings)
    db = client.app.state.deps.db
    old = now() - timedelta(minutes=20)
    db.create_case(Case(id="s2", owner_email="a@x.com", status="READING", created_at=old, updated_at=old,
                        progress={"step": "READING", "done": 3, "total": 9, "label": "x"}))
    [row] = [r for r in client.get("/api/cases", headers=A).json() if r["id"] == "s2"]
    assert row["status"] == "FAILED" and row["progress"] is None
    case = db.get_case("s2")
    assert case.finished_at is not None and case.error.startswith("Analysis was interrupted")


def test_progress_write_failure_does_not_fail_the_case(tmp_path):
    deps = _deps(tmp_path)
    original = deps.db.update_case

    def flaky(case_id, **fields):
        if set(fields) == {"progress"}:  # a progress-only (cosmetic) write
            raise RuntimeError("deadline exceeded")
        return original(case_id, **fields)

    deps.db.update_case = flaky
    run_pipeline(_new_case(deps), deps)
    assert deps.db.get_case("c1").status == "READY"


def test_status_and_progress_share_writes(tmp_path):
    deps = _deps(tmp_path)
    case_id = _new_case(deps)
    calls, original = [], deps.db.update_case
    deps.db.update_case = lambda c, **k: calls.append(set(k)) or original(c, **k)
    run_pipeline(case_id, deps)
    from claimlens.pipeline.checks import ALL_CHECKS

    # 4 status writes (each carrying progress) + extracting + one per check + per file's first page + the last page
    assert len(calls) <= 4 + 1 + len(ALL_CHECKS) + 2 + 1
    assert {"status"} not in calls  # every status change carries its progress


def test_files_are_fetched_one_at_a_time(settings, monkeypatch):
    """Up to 40 files of 20 MB: fetch each just before reading it, never all of them first."""
    from tests.conftest import upload_case

    client = _client(settings)
    deps = client.app.state.deps
    events = []
    get, read = deps.storage.get, __import__("claimlens.pipeline.run", fromlist=["read_document"]).read_document

    def fetch(key):
        if "/pages/" not in key:
            events.append(("get", key.rsplit("/", 1)[-1]))
        return get(key)

    def reading(doc, data, name, *a, **kw):
        events.append(("read", name))
        return read(doc, data, name, *a, **kw)

    monkeypatch.setattr(deps.storage, "get", fetch)
    monkeypatch.setattr("claimlens.pipeline.run.read_document", reading)
    assert upload_case(client).status_code == 200
    kinds = [kind for kind, _ in events if kind in ("get", "read")]
    assert kinds[:4] == ["get", "read", "get", "read"]
