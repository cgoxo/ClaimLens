"""Run again the checks that need no AI, after a reviewer corrected a fact."""
from claimlens.models import Finding
from claimlens.pipeline.checks.cards import duplicate_pages
from claimlens.pipeline.checks.coverage import CODE_COVERAGE_CODES, coverage_code_findings
from claimlens.pipeline.checks.duplicate import check_duplicate
from claimlens.pipeline.checks.story import check_story
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.prove import prove

# the checks and codes recheck owns; every other finding is kept untouched
RECHECKED = {"story", "duplicate"} | CODE_COVERAGE_CODES


def is_owned(finding: Finding) -> bool:
    return finding.check in RECHECKED or finding.code in RECHECKED


def recheck(ctx: Ctx) -> list[Finding]:
    """Story, duplicate and the code-only coverage findings from the current facts. Never calls the AI."""
    ctx.skip_pages = {("claim", later.page) for _, later in duplicate_pages(ctx.read)}
    kept, _ = prove(ctx, check_story(ctx) + check_duplicate(ctx) + coverage_code_findings(ctx))
    return kept
