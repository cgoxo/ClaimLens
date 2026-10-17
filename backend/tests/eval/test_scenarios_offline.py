"""Every scenario through the real product (upload API, document check, pipeline, prove, report), with an AI
stand-in that returns the true facts. Results must match the truth exactly."""

import numpy as np
import pytest

from eval.scenarios.forgeries import FORGERIES, pick
from eval.scenarios.recipe import make_recipe
from eval.scenarios.run import plan
from eval.scenarios.targets import LocalTarget
from eval.scenarios.truth import truth_of

SINGLE = sorted(FORGERIES)


def _check(seed: int, names: list[str], fmt: str, target: LocalTarget):
    recipe = make_recipe(seed, "off")
    for n in names:
        if not FORGERIES[n].needs(recipe):
            pytest.skip(f"{n} needs a different recipe")
        recipe = FORGERIES[n].apply(recipe)
    truth = truth_of(recipe, names, fmt, ocr=False)
    result = target.run(recipe, names, fmt, truth)
    assert result.error is None, result.error
    assert result.status == truth.status, (names, fmt)
    assert result.codes == truth.codes, (names, fmt)
    assert result.band == truth.band, (names, fmt, result.codes)
    assert result.recommendation == truth.recommendation, (names, fmt, result.codes)
    if truth.payable is None:
        assert result.payable is None
    else:
        assert result.payable == pytest.approx(truth.payable, abs=1), (names, fmt)


@pytest.fixture(scope="module")
def target(tmp_path_factory):
    return LocalTarget(tmp_path_factory.mktemp("scenarios"))


@pytest.mark.parametrize("fmt", ["one_pdf", "split_files"])
@pytest.mark.parametrize("name", ["clean", *SINGLE])
def test_every_single_scenario_offline(name, fmt, target):
    seed = 11 if name != "room_over_limit" else 5  # seed 5 has a room limit
    if name == "missing_page":
        seed = 3  # has pharmacy bills
    _check(seed, [] if name == "clean" else [name], fmt, target)


def test_combinations_offline(target):
    rng = np.random.default_rng(42)
    for seed in range(100, 130):
        recipe = make_recipe(seed, "off")
        _check(seed, pick(rng, recipe), str(rng.choice(["one_pdf", "split_files"])), target)


def test_offline_run_matches_truth(target):
    """The scenario run's own plan, 30 seeds: not one payable or recommendation differs from the truth."""
    wrong = []
    for seed, names, fmt, recipe in plan(30, 7, ["one_pdf", "split_files", "photos"], "off"):
        truth = truth_of(recipe, names, fmt, ocr=False)
        result = target.run(recipe, names, fmt, truth)
        assert result.error is None, (seed, result.error)
        if truth.payable is None or result.payable is None:
            paid = truth.payable is None and result.payable is None
        else:
            paid = abs(result.payable - truth.payable) <= 1
        if not paid or result.recommendation != truth.recommendation:
            wrong.append((seed, names, fmt, truth.payable, result.payable, truth.recommendation,
                          result.recommendation))
    assert wrong == []


def test_photos_offline_never_crash(target):
    for seed, names in ((21, []), (22, ["retype_total"]), (23, ["name_typo", "claimed_mismatch"])):
        _check(seed, names, "photos", target)
