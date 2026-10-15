import numpy as np
import pytest

from eval.forensics.score import fused, keep, metrics


def _rows(pos, neg, detector="d", kind="G", base_of=lambda i: i % 10, control_type=None, neg_kind="control"):
    rows = []
    for i, s in enumerate(pos):
        rows.append({"base": base_of(i), "kind": kind, "control_type": None, "field_kind": "amount",
                     "edited": True, "detector": detector, "score": s})
    for i, s in enumerate(neg):
        rows.append({"base": base_of(i), "kind": neg_kind, "control_type": control_type or "original",
                     "field_kind": "amount", "edited": False, "detector": detector, "score": s})
    return rows


def test_perfect_separation_gives_auc_1():
    m = metrics(_rows([0.9] * 200, [0.1] * 200), "d", ("G",))
    assert m["auc"] == 1.0 and m["tpr_at_5fpr"] == 1.0


def test_shuffled_scores_give_auc_near_half():
    rng = np.random.default_rng(0)
    m = metrics(_rows(rng.random(1000), rng.random(1000)), "d", ("G",))
    assert abs(m["auc"] - 0.5) < 0.1


def test_threshold_comes_from_half_a_only():
    rows = _rows([0.9] * 200, list(np.linspace(0, 1, 200)))
    t = metrics(rows, "d", ("G",))["threshold"]
    for r in rows:  # change only half-B negatives
        if not r["edited"] and r["base"] in metrics(rows, "d", ("G",))["half_b"]:
            r["score"] = 0.0
    assert metrics(rows, "d", ("G",))["threshold"] == t


def test_false_positives_are_per_control_type_and_fail_the_keep_rule():
    rows = _rows([0.9] * 200, [0.1] * 200) + _rows([], [0.95] * 40, control_type="bold_total")
    m = metrics(rows, "d", ("G",))
    assert m["fpr_by_control"]["bold_total"] == 1.0 and m["fpr_by_control"]["original"] == 0.0
    assert not keep(m)


def test_no_opinion_is_not_a_negative():
    rows = _rows([0.9] * 100, [0.1] * 100) + _rows([], [None] * 50)
    m = metrics(rows, "d", ("G",))
    assert m["n_no_opinion"] == 50 and m["auc"] == 1.0


def test_negatives_include_unedited_fields_on_forged_images():
    rows = _rows([0.9] * 100, [0.1] * 100) + _rows([], [0.99] * 100, neg_kind="G")
    assert metrics(rows, "d", ("G",))["auc"] < 1.0


def test_keep_rule():
    assert keep({"auc": 0.75, "fpr_by_control": {"original": 0.04, "whatsapp": 0.05}})
    assert not keep({"auc": 0.69, "fpr_by_control": {"original": 0.0}})
    assert not keep({"auc": None, "fpr_by_control": {}})


def test_fused_max_and_mean_ignore_missing():
    rows = [{"image": "i", "field": "f", "detector": "a", "score": 0.2},
            {"image": "i", "field": "f", "detector": "b", "score": 0.8},
            {"image": "i", "field": "f", "detector": "c", "score": None}]
    out = {r["detector"]: r["score"] for r in fused(rows, ["a", "b", "c"])}
    assert out["fused_max"] == 0.8 and out["fused_mean"] == pytest.approx(0.5)


def test_report_shows_each_detector_with_its_verdict_and_cost():
    from eval.forensics.report import render

    good = _rows([0.9] * 200, [0.1] * 200, detector="good") + _rows([0.9] * 200, [], detector="good", kind="G2")
    bad = _rows(list(np.linspace(0, 1, 200)), list(np.linspace(0, 1, 200)), detector="bad")
    for r in good + bad:
        r.update(image=f"{r['detector']}-{r['base']}", field="total", seconds=0.5)
    text = render(good + bad, date="2026-10-16")
    assert "| good | 1.00 |" in text and "KEEP" in text
    assert "| bad |" in text and "DROP" in text
    assert "₹" in text and "Known limits" in text
