# Scenario suite: live (2026-10-16)

100 generated claims (clean, coverage-only, single and combined forgeries, rejections), uploaded through the real API and analysed by the real pipeline.

## Case pass rate: 31/100 (31%)

A case passes with the right status, no missing finding, and no extra finding other than low notes.

## Per finding

| Code | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| bill_outside_cover_window | 22 | 0 | 0 | 100% | 100% |
| charge_unrelated_to_treatment | 21 | 33 | 0 | 39% | 100% |
| charge_unusual_for_treatment | 0 | 60 | 0 | 0% | n/a |
| claimed_amount_mismatch | 31 | 0 | 0 | 100% | 100% |
| date_order | 12 | 0 | 0 | 100% | 100% |
| duplicate_charge | 9 | 0 | 0 | 100% | 100% |
| duplicate_invoice | 14 | 0 | 0 | 100% | 100% |
| duplicate_page_image | 6 | 0 | 0 | 100% | 100% |
| editing_tool | 19 | 0 | 0 | 100% | 100% |
| font_outlier | 11 | 0 | 0 | 100% | 100% |
| hidden_text | 11 | 0 | 0 | 100% | 100% |
| icu_limit | 8 | 0 | 0 | 100% | 100% |
| incomplete_bill | 6 | 0 | 0 | 100% | 100% |
| inpatient_outside_stay | 27 | 0 | 0 | 100% | 100% |
| late_edit | 10 | 0 | 0 | 100% | 100% |
| multiple_saves | 4 | 0 | 0 | 100% | 100% |
| name_mismatch | 24 | 0 | 0 | 100% | 100% |
| non_payable_items | 34 | 0 | 0 | 100% | 100% |
| not_covered | 0 | 6 | 0 | 0% | n/a |
| partly_covered | 0 | 8 | 0 | 0% | n/a |
| policy_number_mismatch | 12 | 1 | 1 | 92% | 92% |
| room_days_exceed_stay | 11 | 0 | 0 | 100% | 100% |
| room_rent_limit | 9 | 0 | 0 | 100% | 100% |
| sum_mismatch | 14 | 0 | 2 | 100% | 88% |
| waiting_period | 10 | 0 | 0 | 100% | 100% |

## Risk band (rows: expected, columns: found)

| | low | review | high | none |
| --- | --- | --- | --- | --- |
| **low** | 30 | 3 | 0 | 0 |
| **review** | 0 | 27 | 2 | 0 |
| **high** | 0 | 1 | 31 | 0 |
| **none** | 0 | 0 | 0 | 6 |

## Payable: 88/94 within ₹1

## Recommendation: 88/94 correct

| (rows: expected, columns: found) | investigate | query | not_payable | approve_part | approve | none |
| --- | --- | --- | --- | --- | --- | --- |
| **investigate** | 31 | 1 | 0 | 0 | 0 | 0 |
| **query** | 2 | 27 | 0 | 0 | 0 | 0 |
| **not_payable** | 0 | 1 | 2 | 0 | 0 | 0 |
| **approve_part** | 0 | 1 | 0 | 20 | 0 | 0 |
| **approve** | 0 | 1 | 0 | 0 | 8 | 0 |

## Policy rules found and proved

| Rule | Cases expected | Found and proved |
| --- | --- | --- |
| waiting_period | 10 | 10 |
| room_rent_limit | 9 | 9 |
| icu_limit | 8 | 8 |
| non_payable_items | 34 | 34 |
| bill_outside_cover_window | 22 | 22 |

Proportionate deduction, deductible, co-pay, sub-limit and the sum-insured cap have no finding code. They are checked through payable accuracy:

| Rule present | Cases | Payable within Rs 1 |
| --- | --- | --- |
| proportionate | 23 | 23 |
| deductible | 32 | 29 |
| co_pay | 26 | 24 |
| sub_limit | 19 | 18 |
| sum_insured_cap | 3 | 3 |

## Rejections: 6/6 right

## By format

| Format | Cases | Passed |
| --- | --- | --- |
| one_pdf | 34 | 11 |
| photos | 33 | 12 |
| split_files | 33 | 8 |

## Worst cases

- seed 70072 one_pdf ['unrelated_charge', 'retype_total', 'wrong_policy_number']: status READY→READY; missing {'sum_mismatch': 1}; extra {'charge_unrelated_to_treatment': 2, 'charge_unusual_for_treatment': 1} (case f2e9aa18a4f0)
- seed 70073 split_files ['retype_total', 'different_name', 'admit_after_discharge']: status READY→READY; missing {'sum_mismatch': 1}; extra {'charge_unusual_for_treatment': 2} (case f219e92738df)
- seed 70080 photos ['pharmacy_after_discharge', 'different_name', 'wrong_policy_number']: status READY→READY; missing {'policy_number_mismatch': 1}; extra {} (case 18dbd8a7301e)
- seed 70043 split_files ['wrong_policy_number', 'duplicate_page', 'claimed_mismatch']: status READY→READY; missing {}; extra {'charge_unrelated_to_treatment': 3, 'charge_unusual_for_treatment': 1, 'partly_covered': 1} (case eb9b39c467db)
- seed 70012 one_pdf ['different_name', 'reused_invoice', 'unrelated_charge']: status READY→READY; missing {}; extra {'charge_unrelated_to_treatment': 2, 'charge_unusual_for_treatment': 1} (case a00b05b30e09)
- seed 70037 split_files ['clean']: status READY→READY; missing {}; extra {'charge_unrelated_to_treatment': 2, 'charge_unusual_for_treatment': 1} (case 4128d72e1468)
- seed 70046 split_files ['duplicate_line', 'editor_resave', 'reused_invoice']: status READY→READY; missing {}; extra {'charge_unrelated_to_treatment': 2, 'charge_unusual_for_treatment': 1} (case 252286f7de55)
- seed 70081 one_pdf ['clean']: status READY→READY; missing {}; extra {'charge_unrelated_to_treatment': 2, 'partly_covered': 1} (case 5976a80cdce0)
- seed 70087 one_pdf ['waiting_period', 'duplicate_page', 'different_name']: status READY→READY; missing {}; extra {'charge_unrelated_to_treatment': 3} (case 42286a1da863)
- seed 70088 split_files ['clean']: status READY→READY; missing {}; extra {'charge_unusual_for_treatment': 2, 'partly_covered': 1} (case 578cda8d1568)

Median time per case: 64.3 s.

## Known issues (not fixed in this release)

- Payable (88/94) and recommendation (88/94) are below the 95% target.
- (A) Gemini's coverage check sometimes repeats a rule that code already applies, such as "consumables not covered (non-payable clause)" and "partly covered (10% co-pay)", so the amount is deducted twice (seeds 70047, 70079, 70088). Fix: ignore coverage verdicts that cite clauses of rules code applies, and say so in the coverage prompt.
- (B) Gemini reads "if a costlier room is chosen, the excess is not payable" as a proportionate-deduction clause, which cuts doctor, surgery and test charges (seeds 70058, 70077). Fix: in the policy prompt, allow proportionate deduction only when the policy says other or associated charges are reduced in proportion.
- (C) The test generator's planted "Spa and massage package" is legitimately excludable as cosmetic (seed 70097). This is a generator fault; pick unrelated items that are not excludable.
- (D) 5 of the 6 recommendation misses came from false flags by the bill-against-story check (charge_unrelated_to_treatment precision 39%, recall 100%; charge_unusual had 60 false positives). The check now ships off (`BILL_STORY=off`).
- (E) One photo case: OCR missed a policy-number mismatch (seed 70080).
- Firestore finding-version history is untested, because the live runner uses a local database. Check it after deploy.
