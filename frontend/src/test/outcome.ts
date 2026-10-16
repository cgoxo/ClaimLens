import type { Citation, Outcome, Settlement } from "../api/types";

export const rule: Citation = { doc: "policy", page: 2, quote: "Room rent is payable up to 1%", bbox: null, source: "page" };

export const settlement: Settlement = {
  lines: [
    {
      bill: 0, line: 0, desc: "Room charges", category: "room", claimed: 13500,
      deductions: [{ amount: 4500, reason: "Room rent above the ₹3,000/day limit", finding_id: "room_rent_limit-policy-1-1", rule }],
      payable: 9000,
    },
    { bill: 0, line: 1, desc: "Surgeon and OT charges", category: "surgery", claimed: 22000, deductions: [], payable: 22000 },
  ],
  claimed: 30000, whole_claim: null, claim_level: [], subtotal: 30000,
  sub_limit: null, deductible: null,
  co_pay: { amount: 3000, reason: "Co-pay 10%", finding_id: null, rule: null },
  si_cap: null, payable: 27000,
  notes: [{ text: "One bill has no date and was left out.", affects_amount: false }],
};

export const outcome = (over: Partial<Outcome> = {}): Outcome => ({
  score: 70, risk: "high", payable: 27000,
  recommendation: { action: "approve_part", reasons: ["Room rent is above the limit."] },
  settlement, ...over,
});
