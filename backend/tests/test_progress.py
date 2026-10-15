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
    for label in ["Reading claim page 1 (1 of 7)", "Reading policy page 3 (7 of 7)", "Extracting facts with Gemini",
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
