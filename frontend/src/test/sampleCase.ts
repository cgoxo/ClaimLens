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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
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
      "verified": true,
      "review": null
    }
  ],
  "pages": [
    {
      "doc": "claim",
      "page": 1,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "claim",
      "page": 2,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "claim",
      "page": 3,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "claim",
      "page": 4,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "policy",
      "page": 1,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "policy",
      "page": 2,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    },
    {
      "doc": "policy",
      "page": 3,
      "kind": "digital",
      "width": 595.2755737304688,
      "height": 841.8897705078125
    }
  ]
};
