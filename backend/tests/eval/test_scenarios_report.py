from eval.scenarios.report import action_matrix, band_matrix, code_table, render, rule_table, silent_rule_table, worst


def _row(expected, found, status=("READY", "READY"), band=("low", "low"), payable=(100.0, 100.0), fmt="one_pdf"):
    return {"seed": 1, "forgeries": [], "fmt": fmt, "expected_codes": expected, "found_codes": found,
            "status_expected": status[0], "status_found": status[1], "band_expected": band[0], "band_found": band[1],
            "payable_expected": payable[0], "payable_found": payable[1], "error": None, "seconds": 2.0, "case_id": "c"}


def test_code_table_counts_tp_fp_fn():
    rows = [_row({"sum_mismatch": 1}, {"sum_mismatch": 1}), _row({"sum_mismatch": 1}, {}),
            _row({}, {"sum_mismatch": 2})]
    t = code_table(rows)["sum_mismatch"]
    assert (t["tp"], t["fp"], t["fn"]) == (1, 2, 1)
    assert t["precision"] == 1 / 3 and t["recall"] == 0.5


def test_zero_denominators_are_na():
    t = code_table([_row({"late_edit": 1}, {})])["late_edit"]
    assert t["precision"] is None and t["recall"] == 0.0


def test_band_matrix_sums_to_n():
    rows = [_row({}, {}, band=("low", "high")), _row({}, {}, band=("review", "review")), _row({}, {})]
    m = band_matrix(rows)
    assert sum(sum(r.values()) for r in m.values()) == 3 and m["low"]["high"] == 1


def test_worst_cases_put_wrong_status_first_then_missing_then_extra():
    a = _row({"x": 1}, {"x": 1, "y": 1})                 # one extra
    b = _row({"x": 2}, {})                               # two missing
    c = _row({}, {}, status=("REJECTED", "READY"))       # wrong status
    assert worst([a, b, c], 3) == [c, b, a]


def test_render_has_the_sections():
    text = render([_row({"sum_mismatch": 1}, {"sum_mismatch": 1})], target="live", date="2026-10-16")
    for section in ("Case pass rate", "Per finding", "Risk band", "Payable", "Rejections", "By format", "Worst"):
        assert section in text


def test_recommendation_counts_and_confusion_table():
    right = {**_row({}, {}), "recommendation_expected": "approve_part", "recommendation_found": "approve_part"}
    wrong = {**_row({}, {}), "recommendation_expected": "query", "recommendation_found": "approve"}
    rejected = _row({}, {}, status=("REJECTED", "REJECTED"))  # no recommendation expected: not counted
    m = action_matrix([right, wrong, rejected])
    assert m["approve_part"]["approve_part"] == 1 and m["query"]["approve"] == 1
    text = render([right, wrong, rejected], target="live", date="2026-10-16")
    assert "Recommendation: 1/2 correct" in text and "| **query** |" in text


def test_rule_table_counts_found_and_proved():
    a = _row({"icu_limit": 1, "room_rent_limit": 1}, {"icu_limit": 1})
    b = _row({"icu_limit": 1}, {"icu_limit": 1})
    t = rule_table([a, b, _row({}, {})])
    assert t["icu_limit"] == {"expected": 2, "proved": 2} and t["room_rent_limit"] == {"expected": 1, "proved": 0}
    assert "Found and proved" in render([a], target="live", date="2026-10-16")


def test_silent_rules_are_reported_through_payable_accuracy():
    ok = {**_row({}, {}, payable=(100.0, 100.0)), "rules": ["co_pay", "deductible"]}
    bad = {**_row({}, {}, payable=(100.0, 90.0)), "rules": ["co_pay"]}
    t = silent_rule_table([ok, bad, _row({}, {})])
    assert t["co_pay"] == {"cases": 2, "payable_ok": 1} and t["deductible"] == {"cases": 1, "payable_ok": 1}
    assert t["sub_limit"] == {"cases": 0, "payable_ok": 0}
    assert "no finding code" in render([ok], target="live", date="2026-10-16")
