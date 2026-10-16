# Policy and Bill Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gemini reads the whole policy into a proved rulebook, sorts bill lines into categories and judges them against the treatment. Code works out an item-by-item settlement and a recommendation, and recalculates both after each review.

**Architecture:**
- The existing `PolicyFacts` model grows into the rulebook: rule models carry `clause/page/quote` and are proved like `WaitingPeriod` is today.
- Every line-level deduction is attached to a coverage finding as `deductions` (so dismissing that finding gives the money back).
- A pure `settle()` turns active findings plus the rulebook into a `Settlement`, and a pure `recommend()` turns that into a `Recommendation`.
- The pipeline stores the first result as `analysis`. The review API recomputes `current`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, rapidfuzz, Vertex Gemini (google-genai), pytest; React 18 + TypeScript + Vitest.

**Spec:** `docs/superpowers/specs/2026-10-16-claimlens-policy-settlement-design.md`

## Global Constraints

- Gemini reads, code decides. Every rupee is computed in code, never taken from a Gemini sum. Percentages are turned into rupees by code from the sum insured.
- Every rule needs `clause`, `page` and `quote`. A rule whose quote isn't on its page is not applied and is listed in `rules_not_verified`.
- Settlement order (spec §6):
  1. Whole-claim exclusion
  2. Not / partly covered items
  3. Non-payables
  4. Room and ICU limits
  5. Proportionate deduction
  6. Pre/post window
  7. Sub-limit
  8. Deductible
  9. Co-pay
  10. Sum-insured cap
- Proportionate deduction reduces `doctor, nursing, surgery, investigations` lines only. It never reduces `medicines, consumables, implants`. These two sets are one constant each in `pipeline/settlement.py`.
- Recommendation precedence (spec §7): investigate > query > not_payable > approve_part > approve. Approve needs payable within ₹1 of claimed.
- New finding codes and severities:
  - `room_days_exceed_stay` high
  - `duplicate_charge` medium
  - `charge_unrelated_to_treatment` medium
  - `charge_unusual_for_treatment` low
  - `bill_story_unavailable` low
  - `icu_limit` coverage
  - `non_payable_items` coverage
  - `bill_outside_cover_window` coverage
  - Deviation from spec §5: `bill_outside_cover_window` is `coverage`, not medium, because it is a policy deduction, not a fraud sign.
- `BILL_STORY=on|off` setting, default `on`. Bill-against-story findings never carry `deductions`.
- Older cases (no rulebook fields, findings without `deductions`) must load and recalculate score and risk without errors.
- Copy is plain English, from the reviewer's side: "Approve in part", "Not payable", "Query", "Investigate".
- The worktree has no venv. Run backend commands from `backend/` as `PYTHONPATH=. /Users/chitresh/Documents/dev/hackii/ClaimLens/backend/.venv/bin/python -m pytest …`, and frontend commands from `frontend/` after `npm ci` once.

## Review Focus

- Money that arrives as text with Indian grouping ("Rs 3,00,000", "₹ 48,500.00") must parse to the right number in every rule. Test in Task 3.
- A percentage rule written as "1% of the sum insured" must become `percent_of_si=1`, which means 1%, and become ₹3,000 on ₹3,00,000. Test in Task 3.
- A line with no amount, or a bill with no date, must be skipped without a crash, and never counted as ₹0 claimed by mistake. Test in Task 8.
- The same item on two different days (two pharmacy bills of "Paracetamol ₹120") is not a duplicate charge. Test in Task 6.
- A case analysed before this change, opened and reviewed after it, must recalculate score and risk and keep its stored payable. Test in Task 10.

---

### Task 1: Models for rules, line categories, deductions, settlement and outcome

**Files:**
- Modify: `backend/claimlens/models.py`
- Test: `backend/tests/test_models_settlement.py`

**Interfaces:**
- Produces, in `claimlens/models.py`:
  - `Category = Literal["room","icu","surgery","doctor","nursing","investigations","medicines","consumables","implants","ambulance","other"]`
  - `class Rule(BaseModel): clause: str = ""; page: int; quote: str`
  - `WaitingPeriod(Rule)`: keeps `condition, months`.
  - `CoPay(Rule)`: `percent: float; applies: Literal["all","age_over","other"] = "all"; age: int | None = None; condition_text: str = ""`
  - `Deductible(Rule)`: `amount: float; per: Literal["claim","year"] = "claim"`
  - `Limit(Rule)`: `amount: float | None = None; percent_of_si: float | None = None`. Per day; `percent_of_si=1` means 1%.
  - `RoomLimit(Limit)`: `room_type_text: str = ""`
  - `SubLimit(Limit)`: `applies_to: str; per: Literal["claim","eye","year"] = "claim"`
  - `Exclusion(Rule)`: `what: str`
  - `NonPayable(Rule)`: `items: list[str] = []; standard_list: bool = False`
  - `Window(Rule)`: `pre_days: int | None = None; post_days: int | None = None`
  - `InitialWaiting(Rule)`: `days: int`
  - `PreExisting(Rule)`: `months: int`
  - `ProportionateDeduction(Rule)`: no extra fields
  - `PolicyFacts` gains, all optional or defaulting to empty:
    - `co_pays: list[CoPay]`
    - `deductible: Deductible | None`
    - `room_limit: RoomLimit | None`
    - `icu_limit: Limit | None`
    - `proportionate_deduction: ProportionateDeduction | None`
    - `sub_limits: list[SubLimit]`
    - `initial_waiting: InitialWaiting | None`
    - `pre_existing: PreExisting | None`
    - `exclusions: list[Exclusion]`
    - `non_payable: NonPayable | None`
    - `window: Window | None`
    - `room_rent_limit_per_day` stays, for older cases.
  - `LineItem` gains `category: Category = "other"; days: Fact | None = None; rate: Fact | None = None`.
  - `ClaimFacts` gains `patient_age: Fact | None = None; room_type: Fact | None = None`.
  - `class LineDeduction(BaseModel): bill: int; line: int; amount: float`. `bill` and `line` are indexes into `ClaimFacts.bills[bill].line_items[line]`. `line = -1` means the whole bill; `bill = -1` means claim level.
  - `Finding` gains `deductions: list[LineDeduction] = []; items: list[str] = []`. The `check` literal adds `"bill_story"`.
  - `class StoryVerdict(BaseModel)`: `item: str; verdict: Literal["fits","unusual","unrelated"]; reason: str = ""; bill_page: int; bill_quote: str; story_page: int | None = None; story_quote: str = ""`
  - `class Deduction(BaseModel)`: `amount: float; reason: str; finding_id: str | None = None; rule: Citation | None = None`
  - `class SettlementLine(BaseModel)`: `bill: int; line: int; desc: str; category: Category; claimed: float; deductions: list[Deduction] = []; payable: float`
  - `class Settlement(BaseModel)`:
    - `lines: list[SettlementLine]; claimed: float | None; whole_claim: Deduction | None = None`
    - `claim_level: list[Deduction] = []; subtotal: float`
    - `sub_limit: Deduction | None = None; deductible: Deduction | None = None; co_pay: Deduction | None = None; si_cap: Deduction | None = None`
    - `payable: float; notes: list[Note] = []`
  - `class Note(BaseModel): text: str; affects_amount: bool = False`
  - `Action = Literal["investigate","query","not_payable","approve_part","approve"]`
  - `class Recommendation(BaseModel): action: Action; reasons: list[str]`
  - `class Outcome(BaseModel): score: int; risk: Literal["low","review","high"]; payable: float | None; recommendation: Recommendation | None = None; settlement: Settlement | None = None`
  - `Case` gains `analysis: Outcome | None = None; current: Outcome | None = None; rules_not_verified: list[dict] = []`
  - `Review.action` adds `"restore"` (stored on versions only; a restored finding has `review=None`).

- [ ] **Step 1: Write failing tests** in `tests/test_models_settlement.py`:
  - `test_old_policy_json_still_validates`: `PolicyFacts.model_validate(json.loads((FAKE_AI/"policy.json").read_text()))` passes, and `co_pays == []`, `room_limit is None`.
  - `test_waiting_period_is_a_rule`: `issubclass(WaitingPeriod, Rule)`.
  - `test_line_item_defaults_to_other`: `LineItem(desc="x").category == "other"`.
  - `test_old_finding_json_has_no_deductions`: `Finding.model_validate({...minimal old finding...}).deductions == []`.
  - `test_case_without_outcomes_validates`: `Case(id="c", owner_email="a@x").analysis is None`.
- [ ] **Step 2: Run** `PYTHONPATH=. …/python -m pytest tests/test_models_settlement.py -q`. Expected: FAIL (ImportError on `Rule`).
- [ ] **Step 3: Add the models above to `models.py`.**
- [ ] **Step 4: Run the new tests and the full suite** (`-m pytest -q`). Expected: all pass.
- [ ] **Step 5: Commit** `feat(models): policy rules, line categories, deductions, settlement and outcome models`

### Task 2: Prove every rule, and record the ones that fail

**Files:**
- Modify: `backend/claimlens/pipeline/extract.py` (`_ground_model`, `extract`)
- Modify: `backend/claimlens/pipeline/context.py` (add `rules_not_verified: list[dict] = field(default_factory=list)`)
- Test: `backend/tests/test_extract.py`

**Interfaces:**
- Consumes: `Rule` (Task 1).
- Produces:
  - `_ground_model(ctx, doc, model, dropped: list[dict] | None = None)`. Any `Rule` instance (not only `WaitingPeriod`) is kept only if `locate(ctx, doc, model.page, model.quote)[0]`.
  - A dropped rule appends `{"rule": type(model).__name__, "clause": model.clause, "page": model.page, "quote": model.quote}` to `dropped`.
  - `extract(ctx)` passes `ctx.rules_not_verified` for the policy.

- [ ] **Step 1: Write failing tests**:
  - `test_rule_with_wrong_quote_is_dropped_and_listed`: build a ctx with `make_ctx`, set the FakeAi policy fixture copy to include `"co_pays": [{"percent": 10, "clause": "9.9", "page": 1, "quote": "no such sentence"}]`, run `extract`, assert `ctx.policy_facts.co_pays == []` and `ctx.rules_not_verified[0]["rule"] == "CoPay"`.
  - `test_rule_with_real_quote_is_kept`: the same with `"quote": "Room rent is payable up to 1% of the sum insured per day"` and `room_limit` with `percent_of_si: 1`. Assert `ctx.policy_facts.room_limit.percent_of_si == 1`.
- [ ] **Step 2: Run** `-m pytest tests/test_extract.py -q`. Expected: the 2 new tests fail.
- [ ] **Step 3: Implement** the `Rule` branch and the `dropped` collector.
- [ ] **Step 4: Run** `tests/test_extract.py` and the full suite. Expected: pass.
- [ ] **Step 5: Commit** `feat(extract): prove every policy rule; list rules not verified`

### Task 3: Rule arithmetic helpers and the standard non-payable list

**Files:**
- Create: `backend/claimlens/pipeline/rules.py`
- Test: `backend/tests/test_rules.py`

**Interfaces:**
- Consumes: Task 1 models; `claimlens.pipeline.text.parse_money` (existing).
- Produces, in `pipeline/rules.py`:
  - `sum_insured(p: PolicyFacts | None) -> float | None`
  - `limit_rupees(limit: Limit | None, p: PolicyFacts | None) -> float | None`: the amount if set, else `percent_of_si / 100 × sum insured`, else `None`.
  - `room_limit_rupees(p) -> tuple[float | None, Citation | None]`: prefers `room_limit`, falls back to the legacy `room_rent_limit_per_day` fact.
  - `icu_limit_rupees(p) -> tuple[float | None, Citation | None]`
  - `STANDARD_NON_PAYABLE: tuple[str, ...]`. At least: gloves, mask, admission kit, admission charges, registration charges, attendant charges, toiletries, food for attendant, cotton, diapers, documentation charges.
  - `is_non_payable(desc: str, p: PolicyFacts | None) -> Citation | None`: fuzzy `partial_ratio ≥ 85` against `p.non_payable.items`, or against `STANDARD_NON_PAYABLE` when `p.non_payable.standard_list`. Returns the rule's citation, or `None`.
  - `rule_citation(rule: Rule) -> Citation` with `doc="policy"`.
  - `stay_nights(f: ClaimFacts) -> int | None`: discharge minus admission, in days.

- [ ] **Step 1: Write failing tests**:
  - `test_percent_of_si_becomes_rupees`: `room_limit=RoomLimit(percent_of_si=1, page=1, quote="q")` with `sum_insured` Fact value `"Rs 3,00,000"` gives `3000.0`.
  - `test_amount_wins_over_percent`: amount 4000 and percent 1 gives 4000.
  - `test_no_sum_insured_percent_gives_none`.
  - `test_legacy_room_fact_used_when_no_rule`: `room_rent_limit_per_day` value `"₹ 3,000"` gives 3000.
  - `test_standard_list_matches_gloves`: "Surgical gloves (2 pairs)" matches when `standard_list=True`, and doesn't when `standard_list=False` and `items=[]`.
  - `test_stay_nights`: admission "10-Mar-2026", discharge "13-Mar-2026" gives 3.
- [ ] **Step 2: Run** `-m pytest tests/test_rules.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `pipeline/rules.py`.**
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit** `feat(rules): rupee limits, non-payable matching, stay length`

### Task 4: Prompts, the new Gemini call, and the fake AI

**Files:**
- Modify: `backend/claimlens/ai.py` (`FACTS_PROMPT`, `POLICY_PROMPT`, new `BILL_STORY_PROMPT`, `Ai` protocol, `VertexGemini`, `FakeAi`; `summarise` signature)
- Modify: `backend/claimlens/settings.py` (`bill_story: Literal["on","off"] = "on"`)
- Modify: `.github/workflows/ci-deploy.yml` (add `BILL_STORY=on` to the env vars list)
- Modify: `backend/eval/scenarios/fake_ai.py` (add `judge_bill_story` returning `self.truth.story_verdicts`; Task 12 fills it) and the `summarise` signature
- Test: `backend/tests/test_ai.py` (create)

**Interfaces:**
- Produces:
  - `Ai.judge_bill_story(story_text: str, items_json: str) -> list[StoryVerdict]`
  - `Ai.summarise(findings: list[Finding], outcome: str = "") -> str`. `outcome` is a plain-text line like "Recommendation: Approve in part. Payable Rs 41,500 of Rs 48,500."
  - `FakeAi.judge_bill_story` reads `bill_story.json` when present, else `[]`.
- Prompt content to add, as plain instruction lines in the existing style:
  - **FACTS_PROMPT:**
    - each line item's `category` from the Category list, with one example per category
    - `days` and `rate` for room and ICU lines, as printed
    - `patient_age` if printed
    - `room_type` as written
  - **POLICY_PROMPT:**
    - every rule in spec §3, each with `clause`, `page` and an exact one-line `quote`
    - percentages as a plain number of percent (`1` for 1%)
    - money as a plain number of rupees
    - `non_payable.standard_list=true` when the policy refers to the regulator's list instead of listing items
    - `null` or `[]` when the policy doesn't have the rule; never invent one
  - **BILL_STORY_PROMPT:** "You check whether each bill line fits the patient's diagnosis and treatment…"; `fits | unusual | unrelated`; quote the bill line exactly (`bill_page`, `bill_quote`); quote what it was judged against (`story_page`, `story_quote`); judge only medical fit, not price; "unusual" only when a doctor would ask about it.

- [ ] **Step 1: Write failing tests**:
  - `test_policy_schema_has_rules`: `"co_pays" in json.dumps(_schema(PolicyFacts))` and `"bbox" not in` it.
  - `test_fake_ai_bill_story_defaults_empty`: `FakeAi(FAKE_AI).judge_bill_story("", "[]") == []`.
  - `test_fake_ai_bill_story_from_fixture`: a tmp copy with `bill_story.json` returns one `StoryVerdict`.
- [ ] **Step 2: Run** `-m pytest tests/test_ai.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the prompts, `judge_bill_story` (via `_ask` with schema `list[StoryVerdict]`), the FakeAi method, the setting and the CI env var.
- [ ] **Step 4: Run** the full suite. Expected: pass.
- [ ] **Step 5: Commit** `feat(ai): full policy rulebook prompt, line categories, bill-against-story call`

### Task 5: Coverage findings carry line deductions

**Files:**
- Modify: `backend/claimlens/pipeline/checks/coverage.py`
- Test: `backend/tests/test_coverage.py`

**Interfaces:**
- Consumes: `rules.py` (Task 3), `LineDeduction` (Task 1).
- Produces:
  - Coverage findings with `deductions` filled, and `items` naming the bill lines.
  - Codes, all severity `coverage`, citation = the rule's clause on the policy page:
    - **`room_rent_limit`:**
      - room lines with `rate > limit`: `(rate − limit) × days` on that line
      - plus, if `proportionate_deduction` was proved, `amount × (1 − limit/rate)` on every `doctor, nursing, surgery, investigations` line
      - one finding
      - `amount_not_payable` = the sum
    - **`icu_limit`:** the same rule for `icu` lines, without proportionate deduction.
    - **`non_payable_items`:** one finding listing every matched line, each deducted in full.
    - **`bill_outside_cover_window`:** one per bill dated before `admission − pre_days` or after `discharge + post_days`. All its lines are deducted (`line=-1`). Only when `window` was proved.
    - **`waiting_period`:** unchanged. `deductions=[LineDeduction(bill=-1, line=-1, amount=claimed)]`.
    - **`not_covered` / `partly_covered`** from `judge_coverage`:
      - each `CoverageItem` maps to the line whose `desc` has `partial_ratio ≥ 80` with `item`
      - otherwise a claim-level `LineDeduction(bill=-1, line=-1, amount=item.amount_not_payable)`
      - a `not_covered` item on a matched line deducts the whole line
  - A room or ICU line without `rate` and `days` facts falls back to `ClaimFacts.room` for room, or makes no deduction.

- [ ] **Step 1: Write failing tests** (extend `test_coverage.py`; build facts directly on `ctx.claim_facts` / `ctx.policy_facts`):
  - `test_room_excess_is_a_line_deduction`: the existing sample gives `room_rent_limit` with one deduction of 4500 on the room line.
  - `test_proportionate_deduction_reduces_doctor_not_medicines`: limit 3000, rate 4500, a doctor line ₹9,000 and a medicines line ₹6,000. The doctor line is deducted 3000 and medicines gets nothing.
  - `test_no_proportionate_without_clause`.
  - `test_icu_limit`: ICU 2 days at ₹12,000, limit 2% of ₹3,00,000. Deducts 12000.
  - `test_non_payable_standard_list`: a "Admission kit" ₹800 line is deducted in full with `standard_list=True`.
  - `test_pharmacy_after_post_window`: `post_days=60`, bill 75 days after discharge, gives one `bill_outside_cover_window` with `line == -1`.
  - `test_not_covered_maps_to_line`: CoverageItem "Cosmetic laser" `not_covered` matches the line "Cosmetic laser therapy" and deducts the whole line.
- [ ] **Step 2: Run** `-m pytest tests/test_coverage.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Keep `_with_box` for citations.
- [ ] **Step 4: Run** the full suite. Expected: pass.
- [ ] **Step 5: Commit** `feat(coverage): every policy deduction is a line deduction on a finding`

### Task 6: Story checks for room days and duplicate charges

**Files:**
- Modify: `backend/claimlens/pipeline/checks/story.py`
- Test: `backend/tests/test_story_duplicate.py`

**Interfaces:**
- Produces, inside `check_story`:
  - **`room_days_exceed_stay` (high):** the sum of `days` on room and ICU lines (or `ClaimFacts.room.days`) is greater than `stay_nights + 1`. Cites the days fact.
  - **`duplicate_charge` (medium):** two lines with the same normalised `desc`, the same amount and the same bill date, across or within bills. Cites the second line's amount fact.

- [ ] **Step 1: Write failing tests**:
  - `test_room_days_exceed_stay`: stay 3 nights and room days 6 give one high finding.
  - `test_room_days_within_tolerance`: 4 days on a 3-night stay gives none.
  - `test_duplicate_charge_same_day`: two "CBC test ₹450" lines on one bill give one medium finding.
  - `test_same_item_different_days_not_duplicate`: two pharmacy bills, different dates, both "Paracetamol ₹120", give none.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite. Expected: pass.
- [ ] **Step 5: Commit** `feat(story): room days against the stay; duplicate charges`

### Task 7: Bill-against-story check (advisory, fails open)

**Files:**
- Create: `backend/claimlens/pipeline/checks/bill_story.py`
- Modify: `backend/claimlens/pipeline/checks/__init__.py` (`ALL_CHECKS = [check_tamper, check_story, check_bill_story, check_duplicate, check_cards, check_coverage]`)
- Modify: `backend/claimlens/pipeline/run.py` (progress label `"Checking the bill against the treatment"` for `bill_story`)
- Test: `backend/tests/test_bill_story.py`

**Interfaces:**
- Consumes: `Ai.judge_bill_story` (Task 4); `StoryVerdict`.
- Produces: `check_bill_story(ctx) -> list[Finding]`:
  - If `settings.bill_story == "off"`, or there are no bills or no diagnosis or procedure: `[]`.
  - Story text = the diagnosis, the procedures, and the visible text of the claim pages whose text contains "discharge summary" (case-insensitive). Items JSON = each line's `desc`, `category`, `amount`, bill page.
  - `unrelated` → `charge_unrelated_to_treatment` (medium). `unusual` → `charge_unusual_for_treatment` (low).
  - `check="bill_story"`; title like `"Chemotherapy charges don't fit the treatment (appendicitis)"`.
  - Detail = the reason + " Check with the hospital."
  - Citation = `Citation(doc="claim", page=v.bill_page, quote=v.bill_quote)`.
  - No `deductions`.
  - On any exception: one `bill_story_unavailable` low finding, with `source="metadata"`, `doc="claim"` and the detail "The check of the bill against the treatment couldn't run." Logged with `log.exception`.

- [ ] **Step 1: Write failing tests**:
  - `test_unrelated_charge_becomes_medium` (fixture `bill_story.json` with one `unrelated`, quote present on claim page 3)
  - `test_fits_makes_nothing`
  - `test_off_setting_skips_call` (an AI stub that raises if called)
  - `test_ai_failure_gives_low_note` (a stub that raises: one `bill_story_unavailable`, case goes on)
  - `test_made_up_quote_dropped_by_prove` (run `prove` on the result; the finding is in `dropped`)
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**, register in `ALL_CHECKS`, add the label.
- [ ] **Step 4: Run** the full suite. `test_pipeline.py` should still pass (the FakeAi has no `bill_story.json`, so it adds nothing).
- [ ] **Step 5: Commit** `feat(checks): bill against the treatment (advisory, fails open)`

### Task 8: Settlement

**Files:**
- Create: `backend/claimlens/pipeline/settlement.py`
- Test: `backend/tests/test_settlement.py`

**Interfaces:**
- Consumes: Task 1 models, `rules.py`.
- Produces:
  - `PROPORTIONATE = ("doctor","nursing","surgery","investigations")` and `NEVER_PROPORTIONATE = ("medicines","consumables","implants")`.
  - `settle(policy: PolicyFacts | None, facts: ClaimFacts | None, findings: list[Finding]) -> Settlement`. `findings` must already exclude dismissed ones; the caller filters.
- Algorithm (the order is the spec's; the body is the implementer's):
  1. `claimed` = `amount_claimed`. One `SettlementLine` per line item with an amount. Lines without an amount are left out, with a note.
  2. A finding with a `LineDeduction(bill=-1, line=-1)` whose amount is at least the claimed amount (`waiting_period`, or `not_covered` on the main treatment as in today's `_main_treatment_excluded`) sets `whole_claim`, and `payable = 0`. Stop.
  3. Apply each finding's line deductions, in finding order. Each is capped at what's left on the line, and records `Deduction(amount, reason=finding.title, finding_id, rule=finding.citations[0])`. `line=-1` deducts all of that bill's lines. `bill=-1` (not whole-claim) goes to `claim_level`.
  4. `subtotal = min(claimed, Σ line payable) − Σ claim_level`. Claimed caps it when bills add up to more than claimed.
  5. Sub-limit: the first `SubLimit` whose `applies_to` has `partial_ratio ≥ 80` with the diagnosis or any procedure caps the subtotal at `limit_rupees`. `per="eye"` or `"year"` is applied once, with a note.
  6. Deductible, then co-pay:
     - `applies="all"` → percent
     - `"age_over"` → only if `patient_age` is greater than `age`; unknown age → `Note(affects_amount=True)`
     - `"other"` → note only
  7. Sum-insured cap, then `payable = round(max(0, …))` to whole rupees.
  8. Missing inputs give notes, never guesses:
     - no claimed amount → `payable` is `None`
     - percentage rule and no sum insured → `Note(affects_amount=True)`
- Rounding: every deduction is rounded to whole rupees once, when it's recorded.

- [ ] **Step 1: Write failing tests** (pure, models built inline):
  - `test_no_rules_pays_claimed`
  - `test_line_deductions_capped_at_line`
  - `test_whole_claim_waiting_period_pays_zero`
  - `test_claimed_caps_subtotal`
  - `test_sub_limit_cataract_40000`
  - `test_deductible_then_copay_order`: claimed 100000, deductible 25000, co-pay 10%, payable 67500.
  - `test_copay_age_over_unknown_age_gives_note`
  - `test_sum_insured_cap`
  - `test_line_without_amount_left_out_with_note`
  - `test_money_strings_parse`: amounts as `"Rs 3,00,000"`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit** `feat(settlement): item-by-item settlement in code`

### Task 9: Recommendation, outcome, and the pipeline's result

**Files:**
- Create: `backend/claimlens/pipeline/outcome.py`
- Modify: `backend/claimlens/pipeline/report.py` (remove `payable` and `_main_treatment_excluded`, which now live in `settlement.py`; `summarise(ctx, findings, outcome_text)`)
- Modify: `backend/claimlens/pipeline/run.py` (Report step)
- Test: `backend/tests/test_outcome.py`; update `backend/tests/test_prove_report.py` and `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `settle` (Task 8), `score`, `risk_band`.
- Produces:
  - `recommend(findings, risk, settlement, policy, facts) -> Recommendation`:
    - **investigate:** risk high, or any active critical finding
    - **query:**
      - risk review
      - `settlement.claimed is None`
      - no sum insured (`rules.sum_insured(policy) is None`, which covers an unreadable policy: reason "The policy couldn't be read" when `policy` is None)
      - an active `unreadable_file` finding
      - any bill `inpatient` and no `discharge_date` fact
      - any note with `affects_amount`
    - **not_payable:** `whole_claim` is set or payable is 0
    - **approve_part:** payable < claimed − 1
    - **approve**
    - `reasons` are plain sentences naming the finding title, deduction or note.
  - `outcome(policy, facts, findings) -> Outcome`. It filters out dismissed findings (`f.review and f.review.action == "dismiss"`), then computes score, risk, settlement and recommendation.
  - `outcome_text(o: Outcome) -> str` for the summary.
- `run.py` Report step:
  - set `step = "SETTLEMENT"` before the call, so a bug fails the case with that step (spec §14)
  - `o = outcome(ctx.policy_facts, ctx.claim_facts, kept)`
  - `update_case(..., score=o.score, risk=o.risk, payable=o.payable, analysis=o, current=o, rules_not_verified=ctx.rules_not_verified, summary=summarise(ctx, kept, outcome_text(o)), ...)`

- [ ] **Step 1: Write failing tests**:
  - `test_recommend_table`: one case per row, each built from small findings and settlements.
  - `test_no_policy_gives_query`: `policy=None` gives `query` with "The policy couldn't be read".
  - `test_dismissed_finding_not_counted`.
  - `test_pipeline_sample_has_analysis`: runs the sample case through `run_pipeline`. `case.analysis.recommendation.action` is one of the five, `case.analysis.settlement.payable == case.payable`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Move payable logic out of `report.py`; fix imports in `test_prove_report.py`.
- [ ] **Step 4: Run** the full suite. Expected: pass.
- [ ] **Step 5: Commit** `feat(outcome): recommendation and stored analysis`

### Task 10: Recalculate after review, restore, and finding versions

**Files:**
- Modify: `backend/claimlens/db.py`:
  - Protocol, `LocalDb` and Firestore: `add_finding_version(case_id: str, fid: str, finding: Finding, action: str, by: str, note: str) -> int` returns the version number
  - `get_finding_versions(case_id: str, fid: str) -> list[dict]`
  - Firestore: subcollection `finding_versions`, number assigned in a transaction as max + 1
- Modify: `backend/claimlens/api.py`:
  - `ReviewIn.action` adds `"restore"`
  - review handler
  - new `GET /api/cases/{case_id}/findings/{fid}/versions`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `outcome` (Task 9).
- Review handler behaviour:
  1. Load the finding. If it has no versions yet, save the current finding as version 1 with action `"analysis"` and by `"pipeline"`.
  2. Apply the change: accept or dismiss sets `review`; restore sets `review=None`.
  3. Save the new finding as the next version.
  4. Recompute `outcome(policy, facts, findings)`:
     - `policy` and `facts` come from `ClaimFacts`/`PolicyFacts.model_validate(case.context["claim"/"policy"])`, if present
     - `update_case(current=o, score=o.score, risk=o.risk, payable=o.payable)`
     - for older cases with no `analysis`, keep the stored `payable` and update score and risk only
  5. If recompute raises: log and return the finding (the review is kept).
- The response stays the finding JSON, plus a `"current"` key with the outcome.

- [ ] **Step 1: Write failing tests**:
  - `test_dismiss_lowers_score_and_restore_brings_it_back` (upload the sample, run inline; dismiss the critical finding, `current.score` drops; restore, it's back)
  - `test_dismiss_room_rent_restores_payable`
  - `test_versions_listed` (after dismiss + restore: versions 1, 2, 3 with actions analysis, dismiss, restore)
  - `test_old_case_review_keeps_payable` (create a case with `analysis=None`, `payable=123`; dismiss; payable still 123, score updated)
  - `test_other_user_cannot_list_versions` (404)
- [ ] **Step 2: Run** `-m pytest tests/test_api.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite. Expected: pass.
- [ ] **Step 5: Commit** `feat(api): recalculate after review, restore, finding versions`

### Task 11: Frontend: recommendation, settlement sheet, rulebook, restore

**Files:**
- Modify: `frontend/src/api/types.ts`. Mirror Task 1: `LineDeduction`, `Deduction`, `SettlementLine`, `Settlement`, `Note`, `Recommendation`, `Outcome`, `Finding.deductions`, `Case.analysis/current/rules_not_verified`, `Review.action` incl. `"restore"`.
- Modify: `frontend/src/api/client.ts` (`review(id, fid, action: "accept" | "dismiss" | "restore", note)`)
- Create: `frontend/src/components/Recommendation.tsx`, `frontend/src/components/SettlementPanel.tsx`, `frontend/src/components/RulebookPanel.tsx`
- Modify: `frontend/src/components/FindingCard.tsx` (Restore button on a dismissed finding), `frontend/src/pages/CasePage.tsx` (header and panels), `frontend/src/styles/app.css`
- Test: `frontend/src/components/SettlementPanel.test.tsx`, `Recommendation.test.tsx`, `FindingCard.test.tsx` (create), `pages/CasePage.test.tsx` (extend)

**Interfaces:**
- `Recommendation({ analysis, current })`:
  - badge labels: investigate "Investigate", query "Query", not_payable "Not payable", approve_part "Approve in part", approve "Approve"
  - reasons as a list
  - when the analysis and current actions or scores differ: "Analysis: HIGH · 70 → After review: REVIEW · 30"
- `SettlementPanel({ settlement, onOpenClause(c: Citation) })`:
  - a table with Item, Type, Claimed, Deducted, Payable
  - each deduction is a row under its line, with its reason and a clause chip (`citationLabel`) that calls `onOpenClause`
  - totals rows for sub-limit, deductible, co-pay, sum-insured cap and "Payable"
  - notes below
  - money in `₹` with `en-IN` grouping
- `RulebookPanel({ policy, notVerified, onOpenClause })`: one row per rule present in `context.policy` (co-pay, deductible, room, ICU, sub-limits, waiting, exclusions, non-payable, window), each with its clause chip; then "Rules not verified".
- `CasePage`:
  - the header shows `Recommendation` beside `RiskStamp`, using `current ?? analysis`
  - "Payable under policy" shows `current.payable`
  - the panels sit under the summary as collapsible `<details>`: "Settlement", open by default; "Policy rules", closed
  - clause chips select a pinned citation in the existing viewer (the same mechanism as `openFact`)
  - after `review()`, the page applies the response's `current` to its data

- [ ] **Step 1: Write failing tests**:
  - `SettlementPanel` renders a deduction reason and "₹4,500", and clicking the clause chip calls `onOpenClause` with that citation.
  - `Recommendation` shows "Approve in part" and the analysis→after-review line when they differ, and not when equal.
  - `FindingCard` shows Restore for a dismissed finding and calls `onReview("restore", "")`.
  - `CasePage` with a READY case shows the badge and the Settlement panel.
- [ ] **Step 2: Run** `npx vitest run`. Expected: the new tests fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npx vitest run && npm run build`. Expected: pass, and the build succeeds.
- [ ] **Step 5: Commit** `feat(frontend): recommendation, settlement sheet, policy rules, restore`

### Task 12: Scenario suite covers the rulebook, settlement and bill-against-story

**Files:**
- Modify: `backend/eval/scenarios/recipe.py`:
  - `Recipe` gains `co_pay`, `co_pay_age`, `deductible`, `sub_limit`, `icu_limit_pct`, `icu_days`, `icu_rate`, `proportionate`, `non_payable_standard`, `consumables`, `pre_days`, `post_days`, `unrelated_item`, `extra_room_days`, `duplicate_line`, `patient_age`
  - `make_recipe` picks them from the seed's RNG so each run mixes them
- Modify: `backend/eval/scenarios/render.py`:
  - `policy_pdf` prints one numbered clause per rule present, in plain sentences
  - `claim_pages` prints the ICU line, the consumables, the unrelated item, the duplicate line and the age
- Modify: `backend/eval/scenarios/forgeries.py` (new forgeries `extra_room_days`, `unrelated_charge`, `duplicate_line`)
- Modify: `backend/eval/scenarios/truth.py`:
  - `policy_facts` returns the full rule set with clause quotes as printed
  - line categories
  - an independent `expected_settlement(r) -> float` and `expected_recommendation(...)`
  - `Truth` gains `recommendation: str` and `story_verdicts: list[StoryVerdict]`
  - `SEVERITY` gains the new codes
- Modify: `backend/eval/scenarios/fake_ai.py` (`judge_bill_story` returns `truth.story_verdicts`)
- Modify: `backend/eval/scenarios/report.py` (adds "Recommendation: n/N correct", a recommendation confusion table, and per-rule "found and proved" counts)
- Test: `backend/tests/eval/` (extend the existing scenario tests)

**Interfaces:**
- `expected_settlement` must be written from the recipe's numbers, not by calling `settle()`. It is the independent check.

- [ ] **Step 1: Write failing tests**:
  - `test_policy_pdf_prints_every_rule` (render a recipe with all rules and assert each clause sentence is in the PDF text)
  - `test_truth_settlement_copay_and_deductible` (a recipe with claimed 100000, deductible 25000, co-pay 10% gives 67500)
  - `test_offline_run_matches_truth`: the existing offline run over 30 seeds with `TruthAi` has 0 payable mismatches and 0 recommendation mismatches
- [ ] **Step 2: Run** `-m pytest tests/eval -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `-m pytest -q` (full) and the offline scenario run (`python -m eval.scenarios.run --help` names the flags; use 100 seeds). Expected: all tests pass, and the offline report shows payable 100% within ₹1 and recommendation 100%.
- [ ] **Step 5: Commit** `test(eval): scenarios for policy rules, settlement, recommendation, bill against story`

### Task 13: Live measurement and docs

**Files:**
- Create: `docs/eval/scenarios-live-<date>.md` (written by the runner)
- Modify: `README.md` ("How a claim is judged" paragraph), `backend/README.md` (new settings `BILL_STORY`)

- [ ] **Step 1:** Run the live scenario suite with real Gemini and Document AI (the same command and target as the 97/100 run of 2026-10-16), at 100 claims.
- [ ] **Step 2:** Check spec §1:
  - payable within ₹1 on at least 95%
  - recommendation correct on at least 95%
  - rules found and proved on at least 95%
  - `charge_unrelated_to_treatment` precision at least 95% and recall at least 80%
  If the bill-against-story check misses its bar, set the CI default `BILL_STORY=off` and say so in the report. If payable or recommendation miss, stop and report the failing cases instead of tuning.
- [ ] **Step 3:** Update the READMEs.
- [ ] **Step 4:** Run the full backend suite, `npx vitest run` and `npm run build`. Expected: all pass.
- [ ] **Step 5: Commit** `docs: live measurement for policy and bill understanding`
