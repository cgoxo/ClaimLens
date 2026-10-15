from eval.scenarios.report import code_table, band_matrix, render, worst


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
