from claimlens.pipeline.checks.bill_story import check_bill_story
from claimlens.pipeline.checks.cards import check_cards
from claimlens.pipeline.checks.coverage import check_coverage
from claimlens.pipeline.checks.duplicate import check_duplicate
from claimlens.pipeline.checks.story import check_story
from claimlens.pipeline.checks.tamper import check_tamper

ALL_CHECKS = [check_tamper, check_story, check_bill_story, check_duplicate, check_cards, check_coverage]
