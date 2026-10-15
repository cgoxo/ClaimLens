from collections import Counter

import numpy as np

from eval.scenarios.forgeries import FORGERIES, pick
from eval.scenarios.recipe import make_recipe
from eval.scenarios.render import render
from eval.scenarios.truth import truth_of


def _truth(names=(), fmt="one_pdf", ocr=True, seed=3):
    recipe = make_recipe(seed, "t1")
    for n in names:
        recipe = FORGERIES[n].apply(recipe)
    return recipe, truth_of(recipe, list(names), fmt, ocr=ocr)


def test_clean_claim():
    recipe, t = _truth()
    assert t.codes == Counter() and t.status == "READY" and t.band == "low"
    assert t.payable == recipe.claimed


def test_waiting_period_pays_nothing_and_stays_low():
    _, t = _truth(["waiting_period"])
    assert t.codes == Counter({"waiting_period": 1}) and t.band == "low" and t.payable == 0


def test_room_over_limit_reduces_payable():
    recipe, t = _truth(["room_over_limit"], seed=5)
    assert t.codes == Counter({"room_rent_limit": 1})
    assert t.payable == recipe.claimed - (recipe.room_rate - recipe.room_limit) * recipe.days


def test_retyped_total():
    _, t = _truth(["retype_total"])
    assert t.codes == Counter({"font_outlier": 1, "hidden_text": 1, "sum_mismatch": 1, "editing_tool": 1})
    assert t.band == "high"  # 40 + 40 + 20 + 20


def test_name_typo_is_low_and_another_person_is_high():
    _, typo = _truth(["name_typo"])
    _, other = _truth(["different_name"])
    assert typo.codes == Counter({"name_mismatch": 1}) and typo.severities["name_mismatch"] == ["low"]
    assert other.severities["name_mismatch"] == ["high"]


def test_rejections_have_no_codes():
    for name in ("cv_in_claim", "bill_in_policy", "policy_in_claim"):
        _, t = _truth([name])
        assert t.status == "REJECTED" and t.codes == Counter() and t.payable is None


def test_photos_without_ocr_are_unreadable_notes_only():
    recipe, t = _truth(fmt="photos", ocr=False)
    files = render(recipe, [], "photos")
    claim_files = [f for f in files if f[0] == "claim"]
    assert t.codes == Counter({"unreadable_file": len(claim_files)}) and t.payable is None


def test_photos_with_ocr_lose_only_pdf_structure_signals():
    _, t = _truth(["retype_total"], fmt="photos", ocr=True)
    assert t.codes == Counter({"sum_mismatch": 1})  # fonts, hidden text, file metadata don't survive a photo


def test_pick_never_combines_conflicts():
    rng = np.random.default_rng(0)
    for _ in range(300):
        chosen = pick(rng)
        for a in chosen:
            assert not (FORGERIES[a].conflicts & set(chosen)), chosen


def test_render_is_deterministic():
    recipe = make_recipe(9, "t1")
    a = render(recipe, ["retype_total"], "split_files")
    b = render(recipe, ["retype_total"], "split_files")
    assert [(c, n) for c, n, _ in a] == [(c, n) for c, n, _ in b]
