# Scenario suite: live (2026-10-16)

100 generated claims (clean, coverage-only, single and combined forgeries, rejections), uploaded through the real API and analysed by the real pipeline.

## Case pass rate: 97/100 (97%)

A case passes with the right status, no missing finding, and no extra finding other than low notes.

## Per finding

| Code | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| claimed_amount_mismatch | 19 | 0 | 0 | 100% | 100% |
| date_order | 6 | 0 | 0 | 100% | 100% |
| duplicate_invoice | 17 | 0 | 0 | 100% | 100% |
| duplicate_page_image | 7 | 0 | 0 | 100% | 100% |
| editing_tool | 26 | 0 | 0 | 100% | 100% |
| font_outlier | 18 | 0 | 0 | 100% | 100% |
| hidden_text | 18 | 0 | 0 | 100% | 100% |
| incomplete_bill | 7 | 0 | 0 | 100% | 100% |
| inpatient_outside_stay | 26 | 0 | 0 | 100% | 100% |
| late_edit | 9 | 0 | 0 | 100% | 100% |
| multiple_saves | 9 | 0 | 0 | 100% | 100% |
| name_mismatch | 21 | 0 | 3 | 100% | 88% |
| policy_number_mismatch | 18 | 0 | 0 | 100% | 100% |
| room_rent_limit | 9 | 0 | 0 | 100% | 100% |
| sum_mismatch | 26 | 0 | 0 | 100% | 100% |
| waiting_period | 12 | 0 | 0 | 100% | 100% |

## Risk band (rows: expected, columns: found)

| | low | review | high | none |
| --- | --- | --- | --- | --- |
| **low** | 32 | 0 | 0 | 0 |
| **review** | 0 | 18 | 0 | 0 |
| **high** | 0 | 1 | 37 | 0 |
| **none** | 0 | 0 | 0 | 12 |

## Payable: 88/88 within ₹1

## Rejections: 12/12 right

## By format

| Format | Cases | Passed |
| --- | --- | --- |
| one_pdf | 34 | 34 |
| photos | 33 | 30 |
| split_files | 33 | 33 |

## Worst cases

- seed 70011 photos ['admit_after_discharge', 'editor_resave', 'different_name']: status READY→READY; missing {'name_mismatch': 1}; extra {} (case a78540e0cb20)
- seed 70020 photos ['name_typo', 'pharmacy_after_discharge', 'incremental_save']: status READY→READY; missing {'name_mismatch': 1}; extra {} (case 04aaeb9f811a)
- seed 70059 photos ['room_over_limit', 'name_typo', 'waiting_period']: status READY→READY; missing {'name_mismatch': 1}; extra {} (case 29c58788857d)

Median time per case: 50.5 s.
