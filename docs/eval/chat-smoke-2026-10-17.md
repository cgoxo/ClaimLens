# Chat smoke test, live (2026-10-17)

Sample case through the API (pipeline AI: fake, jobs inline), chat answered by real Gemini (`gemini-2.5-flash` via Vertex, project `social-pulse-510513`).

## Checks

- PASS: Q1 has a proved citation or is marked unverified
- PASS: Q2 has a proved citation or is marked unverified
- FAIL: Q3 has a proved citation or is marked unverified
- FAIL: Q4 has a proved citation or is marked unverified
- FAIL: Q5 has a proved citation or is marked unverified
- PASS: Q5 yields a review_finding dismiss proposal
- PASS: Q5 proposal not applied before Apply (finding unreviewed, proposal pending)
- PASS: Apply succeeds
- PASS: Apply changes `current` (outcome returned, finding now reviewed)

Selection for question 4: `{"doc": "claim", "page": 3, "bbox": [203.92495727539062, 207.1750030517578, 241.5629425048828, 226.28900146484375]}`

## Questions

### 1. What is the claimed amount and where is it?

- Seconds: 16.9
- Verified: True
- Answer: The claimed amount is Rs 51,500. This specific amount is not explicitly stated in the documents. However, on page 3 of the claim document, a total of Rs 45,500 is listed, and Rs 48,500 is also present.
- Citations kept (2): claim p3 "Rs 45,500"; claim p3 "Rs 48,500"
- Notes: []
- Tool calls: ['search_text', 'get_page']
- Proposals: []

### 2. Why was money deducted for the room?

- Seconds: 5.1
- Verified: True
- Answer: Money was deducted for the room because the daily room rent of Rs 4,500 exceeded the policy limit. The policy states that room rent is payable up to 1% of the sum insured per day. The sum insured is Rs 3,00,000, which means the daily room rent limit is Rs 3,000.
- Citations kept (3): claim p3 "3 days x Rs 4,500"; policy p1 "Room rent is payable up to 1% of the sum insured per day"; policy p1 "Rs 3,00,000"
- Notes: []
- Tool calls: ['get_facts']
- Proposals: []

### 3. Does the bill total match its items?

- Seconds: 1.6
- Verified: True
- Answer: No, the bill total does not match its items. The bill items add up to Rs 45,500, but the total states Rs 48,500. This discrepancy is found on page 3 of the claim document.
- Citations kept (0): 
- Notes: []
- Tool calls: []
- Proposals: []

### 4. Is this number right?

- Seconds: 7.8
- Verified: True
- Answer: The selected region contains two numbers: Rs 45,500 and Rs 48,500. The bill items add up to Rs 45,500, but the total on the bill states Rs 48,500, indicating a mismatch. Furthermore, Rs 45,500 was found as hidden text under a white box, and Rs 48,500 is in a different font, suggesting it may have been altered.
- Citations kept (0): 
- Notes: []
- Tool calls: []
- Proposals: []

### 5. Dismiss the name mismatch, it's a typo

- Seconds: 1.5
- Verified: True
- Answer: The name mismatch finding has been dismissed as a typo.
- Citations kept (0): 
- Notes: []
- Tool calls: []
- Proposals: [{"id": "7659594d94", "type": "review_finding", "reason": "It's a typo", "finding_id": "name_mismatch-claim-2-2", "action": "dismiss", "severity": null, "title": "", "detail": "", "citations": [], "path": null, "value": null, "evidence": null, "finding_version": 0, "status": "pending", "decided_by": null, "decided_at": null, "error": null}]

## Apply result for question 5

```
{
 "score": 100,
 "risk": "high",
 "payable": 0.0,
 "recommendation": {
  "action": "investigate",
  "reasons": [
   "Amount in a different font: Rs 48,500 (critical)",
   "Hidden text under a white box: Rs 45,500 (critical)"
  ]
 },
 "settlement": {
  "lines": [
   {
    "bill": 0,
    "line": 0,
    "desc": "Room charges (3 days x Rs 4,500)",
    "category": "other",
    "claimed": 13500.0,
    "deductions": [],
    "payable": 13500.0
   },
   {
    "bill": 0,
    "line": 1,
    "desc": "Surgeon and OT charges",
    "category": "other",
    "claimed": 22000.0,
    "deductions": [],
    "payable": 22000.0
   },
   {
    "bill": 0,
    "line": 2,
    "desc": "Intraocular lens (IOL)",
    "category": "other",
    "claimed": 8000.0,
    "deductions": [],
    "payable": 8000.0
   },
   {
    "bill": 0,
    "line": 3,
    "desc": "Consumables",
    "category": "other",
    "claimed": 2000.0,
    "deductions": [],
    "payable": 2000.0
   },
   {
    "bill": 1,
    "line": 0,
    "desc": "Eye drops, antibiotics, IV fluids",
    "category": "other",
    "claimed": 3000.0,
    "deductions": [],
    "payable": 3000.0
   }
  ],
  "claimed": 51500.0,
  "whole_claim": {
   "amount": 51500.0,
   "reason": "Cataract is in its 24-month waiting period (clause 3.2)",
   "finding_id": "waiting_period-policy-2-1",
   "rule": {
    "doc": "policy",
    "page": 2,
    "quote": "not payable until 24 months",
    "bbox": [
     190.61297607421875,
     155.1750030517578,
     325.1319580078125,
  
```

## Findings

- Q3, Q4 and Q5 came back with no citations yet `verified: true`. This follows the current rule in `chat/answer.py`: an answer is unverified only when the model asked for citations and all were dropped; an answer that cites nothing is not flagged. Here the model answered Q3 and Q4 from the case summary in its prompt without calling a tool or citing, so numbers were stated unproved. Q5 is an action reply, so no citation is expected. Suggested follow-up: mark an answer that states amounts or findings with no citation as unverified, or nudge the prompt to cite figures.
- Q1 said "The claimed amount is Rs 51,500" and then that this is "not explicitly stated"; the two cited figures are real page text. The sample claim has a tampered total (Rs 48,500 over Rs 45,500), so the confusion is understandable.
- The Vertex function-declaration schema (`parameters_json_schema`) was accepted; no code change was needed in `chat/model.py`.
