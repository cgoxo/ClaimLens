from claimlens.pipeline.checks.tamper import check_tamper
from tests.conftest import make_ctx


def _codes(findings, code):
    return [f for f in findings if f.code == code]


def test_font_outlier(ctx):
    found = _codes(check_tamper(ctx), "font_outlier")
    assert len(found) == 1
    f = found[0]
    assert f.severity == "critical"
    assert (f.citations[0].doc, f.citations[0].page, f.citations[0].quote) == ("claim", 3, "Rs 48,500")


def test_hidden_text(ctx):
    found = _codes(check_tamper(ctx), "hidden_text")
    assert len(found) == 1
    assert found[0].severity == "critical"
    assert found[0].citations[0].page == 3
    assert "Rs 45,500" in found[0].citations[0].quote


def test_editing_tool(ctx):
    findings = check_tamper(ctx)
    tool = _codes(findings, "editing_tool")
    assert len(tool) == 1 and tool[0].severity == "high"
    assert "iLovePDF" in tool[0].detail
    assert tool[0].citations[0].quote == "Claim Form"
    assert not [f for f in _codes(findings, "late_edit") if f.citations[0].doc == "claim"]


def test_clean_claim_has_no_tamper(tmp_path):
    assert check_tamper(make_ctx(tmp_path, claim="claim_clean.pdf")) == []


def test_policy_has_no_tamper(ctx):
    assert not [f for f in check_tamper(ctx) if f.citations[0].doc == "policy"]


def test_finding_ids_unique(ctx):
    ids = [f.id for f in check_tamper(ctx)]
    assert len(ids) == len(set(ids))
