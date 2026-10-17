from claimlens.pipeline.checks.coverage import CODE_COVERAGE_CODES, check_coverage, coverage_code_findings
from claimlens.pipeline.recheck import RECHECKED, recheck
from tests.conftest import make_ctx


class NoAi:
    def __getattr__(self, name):
        raise AssertionError(f"recheck called the AI: {name}")


def _extracted(tmp_path):
    from claimlens.pipeline.extract import extract

    c = make_ctx(tmp_path)
    extract(c)
    return c


def test_check_coverage_unchanged(ctx):
    full = check_coverage(ctx)
    code = coverage_code_findings(ctx)
    assert {f.code for f in code} <= CODE_COVERAGE_CODES
    assert [(f.id, f.amount_not_payable) for f in full[:len(code)]] == [(f.id, f.amount_not_payable) for f in code]
    assert all(f.code not in CODE_COVERAGE_CODES for f in full[len(code):])


def test_recheck_clears_sum_mismatch_after_total_corrected(tmp_path):
    from claimlens.pipeline.checks.story import check_story
    from claimlens.pipeline.text import parse_money

    c = _extracted(tmp_path)
    bill = c.claim_facts.bills[0]
    total = sum(parse_money(i.amount.value) for i in bill.line_items if i.amount)
    bill.total = bill.total.model_copy(update={"value": total + 5000})
    assert any(f.code == "sum_mismatch" for f in check_story(c))
    c.deps.ai = NoAi()
    bill.total = bill.total.model_copy(update={"value": total, "source": "reviewer"})
    assert not any(f.code == "sum_mismatch" for f in recheck(c))


def test_recheck_makes_no_ai_call(tmp_path):
    c = _extracted(tmp_path)
    c.deps.ai = NoAi()
    kept = recheck(c)
    assert all(f.check in RECHECKED or f.code in RECHECKED for f in kept)
