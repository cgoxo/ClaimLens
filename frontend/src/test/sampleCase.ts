// A READY case captured from the backend running on the sample PDFs (AI=fake).
import type { Case } from "../api/types";

export const sampleCase: Case = {
  "id": "cc04f468ff40",
  "owner_email": "you@example.com",
  "status": "READY",
  "step": null,
  "error": null,
  "created_at": "2026-10-10T10:15:38.260028Z",
  "updated_at": "2026-10-10T10:15:38.448841Z",
  "files": {
    "claim": "cases/cc04f468ff40/claim.pdf",
    "policy": "cases/cc04f468ff40/policy.pdf"
  },
  "score": 100,
  "risk": "high",
  "payable": 0.0,
  "summary": "High risk: the bill total was edited and the invoice was used in an earlier claim. Cataract is in its 24-month waiting period.",
  "dropped_findings": [],
  "progress": null,
  "cards": [
    { "id": "claim", "role": "claim", "label": "Claim", "files": [{ "name": "claim.pdf", "pages": 0 }] },
    { "id": "policy", "role": "policy", "label": "Policy", "files": [{ "name": "policy.pdf", "pages": 0 }] }
  ],
  "finished_at": "2026-10-15T19:13:35.028353Z",
  "seen_at": null,
  "findings_count": 8,
  "context": {"claim":{"policy_number":{"value":"EH-2025-778812","page":1,"quote":"EH-2025-778812","bbox":[138.03298950195312,83.17500305175781,221.79795837402344,98.28900146484375]},"hospital_name":{"value":"Sunrise Eye & General Hospital, Pune","page":1,"quote":"Sunrise Eye & General Hospital, Pune","bbox":[123.36997985839844,119.17500305175781,309.8419494628906,134.28900146484375]},"claimant_name":{"value":"Rahul Verma","page":1,"quote":"Rahul Verma","bbox":[127.0329818725586,101.17500305175781,191.21795654296875,116.28900146484375]},"admission_date":{"value":"10-Mar-2026","page":1,"quote":"Date of admission: 10-Mar-2026","bbox":[50.0,137.1750030517578,207.11294555664062,152.28900146484375]},"discharge_date":{"value":"13-Mar-2026","page":1,"quote":"Date of discharge: 13-Mar-2026","bbox":[50.0,155.1750030517578,205.2869415283203,170.28900146484375]},"claim_date":{"value":"22-Mar-2026","page":1,"quote":"Date of claim: 22-Mar-2026","bbox":[50.0,191.1750030517578,195.4969482421875,206.28900146484375]},"amount_claimed":{"value":51500.0,"page":1,"quote":"Rs 51,500","bbox":[144.14898681640625,173.1750030517578,194.28697204589844,188.28900146484375]},"diagnosis":{"value":"Senile cataract, right eye","page":2,"quote":"Senile cataract, right eye","bbox":[116.63798522949219,155.1750030517578,237.6929473876953,170.28900146484375]},"names":[{"value":"Rahul Verma","page":1,"quote":"Rahul Verma","bbox":[127.0329818725586,101.17500305175781,191.21795654296875,116.28900146484375]},{"value":"Rahul Varma","page":2,"quote":"Rahul Varma","bbox":[123.9859848022461,83.17500305175781,188.17095947265625,98.28900146484375]},{"value":"Rahul Verma","page":3,"quote":"Rahul Verma","bbox":[90.35899353027344,83.17500305175781,154.54397583007812,98.28900146484375]},{"value":"Rahul Verma","page":4,"quote":"Rahul Verma","bbox":[90.35899353027344,101.17500305175781,154.54397583007812,116.28900146484375]}],"procedures":[{"name":{"value":"Phacoemulsification with IOL implant","page":2,"quote":"Phacoemulsification with IOL implant","bbox":[119.09098052978516,173.1750030517578,298.8199462890625,188.28900146484375]},"date":{"value":"11-Mar-2026","page":2,"quote":"(11-Mar-2026)","bbox":[301.8779602050781,173.1750030517578,372.16790771484375,188.28900146484375]}}],"room":{"rate_per_day":{"value":4500.0,"page":3,"quote":"3 days x Rs 4,500","bbox":[128.24298095703125,119.17500305175781,216.28695678710938,134.28900146484375]},"days":{"value":3.0,"page":3,"quote":"3 days x Rs 4,500","bbox":[128.24298095703125,119.17500305175781,216.28695678710938,134.28900146484375]}},"bills":[{"page":3,"kind":"hospital","invoice_no":{"value":"INV-SEH-2026-0412","page":3,"quote":"INV-SEH-2026-0412","bbox":[205.87997436523438,43.94999694824219,343.429931640625,64.6050033569336]},"date":{"value":"13-Mar-2026","page":3,"quote":"Bill date: 13-Mar-2026","bbox":[179.00796508789062,83.17500305175781,287.2149353027344,98.28900146484375]},"inpatient":true,"line_items":[{"desc":"Room charges (3 days x Rs 4,500)","amount":{"value":13500.0,"page":3,"quote":"Rs 13,500","bbox":[241.35594177246094,119.17500305175781,291.49395751953125,134.28900146484375]}},{"desc":"Surgeon and OT charges","amount":{"value":22000.0,"page":3,"quote":"Rs 22,000","bbox":[225.4939422607422,137.1750030517578,275.6319274902344,152.28900146484375]}},{"desc":"Intraocular lens (IOL)","amount":{"value":8000.0,"page":3,"quote":"8,000","bbox":[224.85594177246094,155.1750030517578,252.3779296875,170.28900146484375]}},{"desc":"Consumables","amount":{"value":2000.0,"page":3,"quote":"2,000","bbox":[248.1099395751953,137.1750030517578,275.6319274902344,152.28900146484375]}}],"total":{"value":48500.0,"page":3,"quote":"Rs 48,500","bbox":[189.42495727539062,210.20599365234375,234.0409698486328,224.8800048828125]}},{"page":4,"kind":"pharmacy","invoice_no":{"value":"PH-7781","page":4,"quote":"PH-7781","bbox":[86.0689926147461,83.17500305175781,129.47499084472656,98.28900146484375]},"date":{"value":"15-Mar-2026","page":4,"quote":"Date: 15-Mar-2026","bbox":[166.1709747314453,83.17500305175781,258.4829406738281,98.28900146484375]},"inpatient":true,"line_items":[{"desc":"Eye drops, antibiotics, IV fluids","amount":{"value":3000.0,"page":4,"quote":"3,000","bbox":[237.69297790527344,155.1750030517578,265.2149658203125,170.28900146484375]}}],"total":{"value":3000.0,"page":4,"quote":"3,000","bbox":[237.69297790527344,155.1750030517578,265.2149658203125,170.28900146484375]}}]},"policy":{"insurer_name":{"value":"Example Health Insurance Co.","page":1,"quote":"Example Health Insurance Co.","bbox":[50.0,43.94999694824219,265.0699768066406,64.6050033569336]},"policy_number":{"value":"EH-2025-778812","page":1,"quote":"EH-2025-778812","bbox":[147.2069854736328,83.17500305175781,230.97195434570312,98.28900146484375]},"start_date":{"value":"01-Jan-2026","page":1,"quote":"01-Jan-2026","bbox":[143.5439910888672,119.17500305175781,205.29795837402344,134.28900146484375]},"sum_insured":{"value":300000.0,"page":1,"quote":"Rs 3,00,000","bbox":[145.3809814453125,155.1750030517578,204.69296264648438,170.28900146484375]},"room_rent_limit_per_day":{"value":3000.0,"page":1,"quote":"Room rent is payable up to 1% of the sum insured per day","bbox":[50.0,209.1750030517578,333.68994140625,224.28900146484375]},"waiting_periods":[{"condition":"Cataract","months":24,"clause":"3.2","page":2,"quote":"not payable until 24 months"}]},"policy_age_months":2},
  "findings": [
    {
      "id": "font_outlier-claim-3-1",
      "check": "tamper",
      "code": "font_outlier",
      "severity": "critical",
      "title": "Amount in a different font: Rs 48,500",
      "detail": "'Rs 48,500' uses Times-Roman 11.0pt; other amounts on this page use Helvetica 11.0pt.",
      "citations": [
        {
          "doc": "claim",
          "page": 3,
          "quote": "Rs 48,500",
          "bbox": [
            189.42495727539062,
            213.10609436035156,
            234.0409698486328,
            224.10609436035156
          ],
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "hidden_text-claim-3-1",
      "check": "tamper",
      "code": "hidden_text",
      "severity": "critical",
      "title": "Hidden text under a white box: Rs 45,500",
      "detail": "'Rs 45,500' is covered by a white box drawn on top of it.",
      "citations": [
        {
          "doc": "claim",
          "page": 3,
          "quote": "Rs 45,500",
          "bbox": [
            189.42495727539062,
            212.39373779296875,
            239.5629425048828,
            223.39373779296875
          ],
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "duplicate_invoice-claim-3-1",
      "check": "duplicate",
      "code": "duplicate_invoice",
      "severity": "critical",
      "title": "Invoice INV-SEH-2026-0412 was already used in claim CLM-1043",
      "detail": "Invoice INV-SEH-2026-0412 appears in an earlier claim (CLM-1043).",
      "citations": [
        {
          "doc": "claim",
          "page": 3,
          "quote": "INV-SEH-2026-0412",
          "bbox": [
            205.87997436523438,
            43.94999694824219,
            343.429931640625,
            64.6050033569336
          ],
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "editing_tool-claim-1-1",
      "check": "tamper",
      "code": "editing_tool",
      "severity": "high",
      "title": "File was saved with an editing tool (iLovePDF)",
      "detail": "The claim file says it was produced by iLovePDF. created 13-Mar-2026, modified 20-Mar-2026",
      "citations": [
        {
          "doc": "claim",
          "page": 1,
          "quote": "Claim Form",
          "bbox": [
            50.0,
            48.3442268371582,
            132.51499938964844,
            63.3442268371582
          ],
          "source": "metadata"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "sum_mismatch-claim-3-1",
      "check": "story",
      "code": "sum_mismatch",
      "severity": "high",
      "title": "Bill items add up to Rs 45,500, total says Rs 48,500",
      "detail": "Line items on page 3 sum to Rs 45,500.",
      "citations": [
        {
          "doc": "claim",
          "page": 3,
          "quote": "Rs 48,500",
          "bbox": [
            189.42495727539062,
            210.20599365234375,
            234.0409698486328,
            224.8800048828125
          ],
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "inpatient_outside_stay-claim-4-2",
      "check": "story",
      "code": "inpatient_outside_stay",
      "severity": "high",
      "title": "Inpatient pharmacy bill dated 15-Mar is outside the hospital stay",
      "detail": "The patient was in hospital 10-Mar to 13-Mar-2026.",
      "citations": [
        {
          "doc": "claim",
          "page": 4,
          "quote": "Date: 15-Mar-2026",
          "bbox": [
            166.1709747314453,
            83.17500305175781,
            258.4829406738281,
            98.28900146484375
          ],
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "name_mismatch-claim-2-2",
      "check": "story",
      "code": "name_mismatch",
      "severity": "low",
      "title": "Name mismatch: Rahul Varma vs Rahul Verma",
      "detail": "Possible typo.",
      "citations": [
        {
          "doc": "claim",
          "page": 2,
          "quote": "Rahul Varma",
          "bbox": [
            123.9859848022461,
            83.17500305175781,
            188.17095947265625,
            98.28900146484375
          ],
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "waiting_period-policy-2-1",
      "check": "coverage",
      "code": "waiting_period",
      "severity": "coverage",
      "title": "Cataract is in its 24-month waiting period (clause 3.2)",
      "detail": "The policy started 01-Jan-2026; treatment on 11-Mar-2026 is only 2 months later.",
      "citations": [
        {
          "doc": "policy",
          "page": 2,
          "quote": "not payable until 24 months",
          "bbox": null,
          "source": "page"
        }
      ],
      "amount_not_payable": 0.0,
      "items": [],      "verified": true,
      "review": null
    },
    {
      "id": "room_rent_limit-policy-1-1",
      "check": "coverage",
      "code": "room_rent_limit",
      "severity": "coverage",
      "title": "Room rent above the Rs 3,000/day limit",
      "detail": "Room at Rs 4,500/day for 3 days: Rs 4,500 is not payable.",
      "citations": [
        {
          "doc": "policy",
          "page": 1,
          "quote": "Room rent is payable up to 1% of the sum insured per day",
          "bbox": null,
          "source": "page"
        }
      ],
      "amount_not_payable": 4500.0,
      "items": [],      "verified": true,
      "review": null
    }
  ],
  "pages": [
    {
      "doc": "claim",
      "page": 1,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "claim",
      "page": 2,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "claim",
      "page": 3,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "claim",
      "page": 4,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "policy",
      "page": 1,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "policy",
      "page": 2,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "policy",
      "page": 3,
      "card_id": null,
      "file_index": 0,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    }
  ]
};
