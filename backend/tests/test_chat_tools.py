import io
import json

from PIL import Image

from claimlens.chat.tools import TOOLS, run_tool
from claimlens.pipeline.read import DPI
from claimlens.pipeline.run import run_pipeline
from claimlens.pipeline.saved import case_ctx
from tests.test_pipeline import _deps, _new_case


def _setup(tmp_path):
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    case = deps.db.get_case("c1")
    return deps, case, case_ctx(deps, case)


def test_search_finds_total(tmp_path):
    deps, case, ctx = _setup(tmp_path)
    out = json.loads(run_tool("search_text", {"query": "TOTAL"}, deps, case, ctx).text)
    assert 0 < len(out["hits"]) <= 10
    assert all("total" in h["snippet"].lower() and h["doc"] and h["page"] for h in out["hits"])


def test_get_page_truncates_long_text(tmp_path, monkeypatch):
    deps, case, ctx = _setup(tmp_path)
    page = next(p for p in ctx.read.pages if len(p.text) > 200)
    monkeypatch.setattr(deps.settings, "chat_tool_chars", 50)
    out = run_tool("get_page", {"doc": page.doc, "page": page.page}, deps, case, ctx)
    assert out.text.endswith("[truncated]")
    assert len(out.text) <= 50 + len(" [truncated]")


def test_list_findings_hides_removed(tmp_path):
    deps, case, ctx = _setup(tmp_path)
    findings = deps.db.get_findings("c1")
    assert len(findings) > 1
    gone = findings[0]
    deps.db.update_finding("c1", gone.id, removed=True)
    out = json.loads(run_tool("list_findings", {}, deps, case, ctx).text)["findings"]
    assert gone.id not in [f["id"] for f in out]
    assert len(out) == len(findings) - 1
    assert {"id", "code", "severity", "title", "status", "citation"} <= set(out[0])
    one = json.loads(run_tool("get_finding", {"finding_id": out[0]["id"]}, deps, case, ctx).text)
    assert "versions" in one


def test_view_region_returns_png_crop(tmp_path):
    deps, case, ctx = _setup(tmp_path)
    page = ctx.read.pages[0]
    whole = run_tool("view_region", {"doc": page.doc, "page": page.page}, deps, case, ctx)
    crop = run_tool("view_region", {"doc": page.doc, "page": page.page, "bbox": [50, 50, 200, 100]}, deps, case, ctx)
    full, small = Image.open(io.BytesIO(whole.image)), Image.open(io.BytesIO(crop.image))
    assert small.format == "PNG" and small.width < full.width and small.height < full.height
    assert abs(small.width - 150 * 1.08 * DPI / 72) < 4


def test_check_region_refuses_digital_page(tmp_path):
    deps, case, ctx = _setup(tmp_path)
    page = next(p for p in ctx.read.pages if p.kind == "digital")
    out = run_tool("check_region", {"doc": page.doc, "page": page.page, "bbox": [50, 50, 200, 100]}, deps, case, ctx)
    assert json.loads(out.text) == {"error": "only for photo or scanned pages"}


def test_unknown_tool_is_error_not_exception(tmp_path):
    deps, case, ctx = _setup(tmp_path)
    assert "error" in json.loads(run_tool("nope", {}, deps, case, ctx).text)
    assert "error" in json.loads(run_tool("get_page", {"doc": "claim"}, deps, case, ctx).text)
    assert "error" in json.loads(run_tool("view_region", {"doc": "claim", "page": 999}, deps, case, ctx).text)
    assert "error" in json.loads(run_tool("final_answer", {}, deps, case, ctx).text)


def test_declarations_are_plain_dicts():
    names = [t["name"] for t in TOOLS]
    assert names == ["search_text", "get_page", "list_findings", "get_finding", "get_facts", "get_settlement",
                     "view_region", "check_region", "final_answer"]
    json.dumps(TOOLS)
