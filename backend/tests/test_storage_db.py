import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

from claimlens.db import LocalDb
from claimlens.models import Case, Finding, PageInfo
from claimlens.storage import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "files")


@pytest.fixture
def db(tmp_path):
    return LocalDb(tmp_path / "db")


def test_storage_round_trip(storage):
    storage.put("cases/c1/claim.pdf", b"%PDF-1", "application/pdf")
    assert storage.exists("cases/c1/claim.pdf")
    assert storage.get("cases/c1/claim.pdf") == b"%PDF-1"


def test_storage_missing_key_raises(storage):
    assert not storage.exists("nope")
    with pytest.raises(KeyError):
        storage.get("nope")


def test_case_create_get_update(db):
    db.create_case(Case(id="c1", owner_email="a@x.com"))
    before = db.get_case("c1").updated_at
    updated = db.update_case("c1", status="READING")
    assert updated.status == "READING"
    assert updated.updated_at >= before
    assert db.get_case("c1").status == "READING"
    assert db.get_case("missing") is None


def test_list_cases_newest_first_and_owner_only(db):
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    db.create_case(Case(id="old", owner_email="a@x.com", created_at=t0))
    db.create_case(Case(id="new", owner_email="a@x.com", created_at=t0 + timedelta(hours=1)))
    db.create_case(Case(id="other", owner_email="b@x.com", created_at=t0))
    assert [c.id for c in db.list_cases("a@x.com")] == ["new", "old"]
    assert db.count_cases_since("a@x.com", t0 + timedelta(minutes=30)) == 1


def test_findings_replace_and_update(db):
    db.create_case(Case(id="c1", owner_email="a@x.com"))
    f = Finding(id="f1", check="story", code="sum_mismatch", severity="high", title="t")
    db.put_findings("c1", [f, f.model_copy(update={"id": "f2"})])
    db.put_findings("c1", [f])
    assert [x.id for x in db.get_findings("c1")] == ["f1"]
    assert db.update_finding("c1", "f1", verified=True).verified is True
    assert db.update_finding("c1", "nope", verified=True) is None


def test_pages_round_trip(db):
    p = PageInfo(doc="claim", page=1, kind="digital", width=595, height=842, png_key="k")
    db.put_pages("c1", [p])
    assert db.get_pages("c1") == [p]


def test_invoice_get_put(db):
    assert db.get_invoice("INVSEH20260412") is None
    db.put_invoice("INVSEH20260412", {"case_id": "CLM-1043"})
    assert db.get_invoice("INVSEH20260412") == {"case_id": "CLM-1043"}


def test_concurrent_updates(db, tmp_path):
    db.create_case(Case(id="c1", owner_email="a@x.com"))
    threads = [threading.Thread(target=db.update_case, args=("c1",), kwargs={"step": str(i)}) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for path in (tmp_path / "db").rglob("*.json"):
        json.loads(path.read_text())
