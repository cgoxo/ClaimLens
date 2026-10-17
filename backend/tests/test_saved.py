from claimlens.pipeline.run import run_pipeline
from claimlens.pipeline.saved import case_ctx, load_read
from tests.test_pipeline import _deps, _new_case


def _run(tmp_path):
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    return deps


def test_round_trip_after_pipeline(tmp_path, monkeypatch):
    from claimlens.pipeline import run as run_mod
    seen = []
    real = run_mod.save_read
    monkeypatch.setattr(run_mod, "save_read", lambda storage, cid, read: (seen.append(read), real(storage, cid, read)))
    deps = _run(tmp_path)
    original = seen[-1]
    loaded = load_read(deps, "c1")
    assert len(original.spans) > 0 and len(original.files) > 0
    assert len(loaded.spans) == len(original.spans)
    assert len(loaded.hidden_layer) == len(original.hidden_layer)
    assert len(loaded.drawings) == len(original.drawings)
    assert loaded.files == original.files
    assert loaded.spans == original.spans
    assert loaded.drawings == original.drawings
    assert len(loaded.pages) == 7


def test_missing_file_gives_pages_only(tmp_path):
    deps = _run(tmp_path)
    (tmp_path / "files" / "cases" / "c1" / "read.json.gz").unlink()
    loaded = load_read(deps, "c1")
    assert len(loaded.pages) == 7
    assert loaded.spans == [] and loaded.files == []


def test_case_ctx_has_facts(tmp_path):
    deps = _run(tmp_path)
    ctx = case_ctx(deps, deps.db.get_case("c1"))
    assert ctx.claim_facts.amount_claimed is not None
    assert ctx.policy_facts is not None
    assert ctx.cards == []
    assert ctx.case_id == "c1" and ctx.deps is deps
