// Written by voice.mjs: every narration line, its clip and when it plays (seconds from the scene's start)
export type VoiceLine = { text: string; file: string; from: number; to: number };
export const VOICE_LINES: Record<string, VoiceLine[]> = {
  "hook": [
    {
      "text": "Look at this hospital bill.",
      "file": "voice/hook/0.wav",
      "from": 0.5,
      "to": 2.12
    },
    {
      "text": "The real total is hidden under a white box, and a bigger one is typed on top.",
      "file": "voice/hook/1.wav",
      "from": 2.57,
      "to": 7.47
    },
    {
      "text": "Would your team catch it?",
      "file": "voice/hook/2.wav",
      "from": 7.92,
      "to": 9.21
    }
  ],
  "why": [
    {
      "text": "In India alone, health insurers lose up to ten thousand crore rupees a year to fraud, waste and abuse.",
      "file": "voice/why/0.wav",
      "from": 0.45,
      "to": 6.85
    },
    {
      "text": "That's across more than three crore claims a year.",
      "file": "voice/why/1.wav",
      "from": 7.3,
      "to": 10.05
    },
    {
      "text": "And with AI, faking a bill gets easier every day.",
      "file": "voice/why/2.wav",
      "from": 10.5,
      "to": 13.94
    }
  ],
  "problem": [
    {
      "text": "Across Asia-Pacific, claims arrive as PDFs, scans and phone photos.",
      "file": "voice/problem/0.wav",
      "from": 0.45,
      "to": 5.67
    },
    {
      "text": "No reviewer can check every page.",
      "file": "voice/problem/1.wav",
      "from": 6.12,
      "to": 8.23
    },
    {
      "text": "So we built ClaimLens.",
      "file": "voice/problem/2.wav",
      "from": 8.68,
      "to": 10.29
    },
    {
      "text": "Gemini reads. Code decides. Every claim is proved.",
      "file": "voice/problem/3.wav",
      "from": 10.74,
      "to": 14.87
    }
  ],
  "upload": [
    {
      "text": "Sign in with Google, and drop in the claim and the policy.",
      "file": "voice/upload/0.wav",
      "from": 0.45,
      "to": 3.86
    },
    {
      "text": "ClaimLens reads every page, and runs OCR on photos with Document AI.",
      "file": "voice/upload/1.wav",
      "from": 9.1,
      "to": 14.25
    },
    {
      "text": "It confirms these are real insurance documents, then Gemini extracts the facts.",
      "file": "voice/upload/2.wav",
      "from": 14.7,
      "to": 20.22
    },
    {
      "text": "In under a minute, the case file is ready.",
      "file": "voice/upload/3.wav",
      "from": 20.67,
      "to": 23.04
    }
  ],
  "results": [
    {
      "text": "Risk: one hundred out of one hundred. Recommendation: investigate.",
      "file": "voice/results/0.wav",
      "from": 0.45,
      "to": 5.01
    },
    {
      "text": "Every fact links back to the page it came from.",
      "file": "voice/results/1.wav",
      "from": 5.46,
      "to": 8.5
    },
    {
      "text": "Every problem is marked on the document: an amount in a different font, the real total hidden underneath,",
      "file": "voice/results/2.wav",
      "from": 9.7,
      "to": 16.33
    },
    {
      "text": "an invoice already used in another claim, even on a phone photo.",
      "file": "voice/results/3.wav",
      "from": 16.78,
      "to": 20.9
    },
    {
      "text": "The policy becomes a rulebook. A waiting period applies, line by line.",
      "file": "voice/results/4.wav",
      "from": 21.35,
      "to": 26.41
    },
    {
      "text": "Payable: zero.",
      "file": "voice/results/5.wav",
      "from": 26.86,
      "to": 28.4
    }
  ],
  "proof": [
    {
      "text": "AI can make things up. So every fact must quote its page.",
      "file": "voice/proof/0.wav",
      "from": 0.45,
      "to": 4.88
    },
    {
      "text": "No quote, no finding.",
      "file": "voice/proof/1.wav",
      "from": 5.4,
      "to": 7.35
    },
    {
      "text": "A different number, or a missing \"not\", never passes.",
      "file": "voice/proof/2.wav",
      "from": 9.8,
      "to": 13.14
    }
  ],
  "agent": [
    {
      "text": "And this is where it becomes agentic.",
      "file": "voice/agent/0.wav",
      "from": 0.45,
      "to": 2.77
    },
    {
      "text": "Reviewers question a Gemini agent that investigates the case with its own tools.",
      "file": "voice/agent/1.wav",
      "from": 3.22,
      "to": 8.14
    },
    {
      "text": "Every answer is checked against the documents.",
      "file": "voice/agent/2.wav",
      "from": 8.6,
      "to": 11.35
    },
    {
      "text": "Draw a box on any page, and ask about just that area.",
      "file": "voice/agent/3.wav",
      "from": 14.1,
      "to": 17.79
    },
    {
      "text": "It does the maths, and spots the total that doesn't fit.",
      "file": "voice/agent/4.wav",
      "from": 18.24,
      "to": 21.43
    },
    {
      "text": "It even proposes changes, but nothing happens until a human approves.",
      "file": "voice/agent/5.wav",
      "from": 24.2,
      "to": 28.82
    },
    {
      "text": "The agent investigates. Code verifies. A human decides.",
      "file": "voice/agent/6.wav",
      "from": 29.3,
      "to": 33.69
    }
  ],
  "cloud": [
    {
      "text": "ClaimLens runs entirely on Google Cloud, in the Mumbai region.",
      "file": "voice/cloud/0.wav",
      "from": 0.45,
      "to": 4.42
    },
    {
      "text": "Firebase signs reviewers in.",
      "file": "voice/cloud/1.wav",
      "from": 4.87,
      "to": 6.8
    },
    {
      "text": "One Cloud Run service hosts the app, the pipeline and the agent, and scales to zero when idle.",
      "file": "voice/cloud/2.wav",
      "from": 7.25,
      "to": 14.1
    },
    {
      "text": "Cloud Tasks runs every analysis reliably. Firestore and Cloud Storage keep the case file.",
      "file": "voice/cloud/3.wav",
      "from": 14.55,
      "to": 21.17
    },
    {
      "text": "Document AI reads the scans. Gemini on Vertex AI reads the meaning.",
      "file": "voice/cloud/4.wav",
      "from": 21.62,
      "to": 26.82
    },
    {
      "text": "Every release ships automatically, with no stored keys.",
      "file": "voice/cloud/5.wav",
      "from": 27.27,
      "to": 30.89
    }
  ],
  "features": [
    {
      "text": "Edited files. Hidden text. Totals that don't add up.",
      "file": "voice/features/0.wav",
      "from": 0.45,
      "to": 4.29
    },
    {
      "text": "Reused invoices. Missing pages. Policy limits.",
      "file": "voice/features/1.wav",
      "from": 4.74,
      "to": 8.75
    },
    {
      "text": "One case file. Every problem, on its page.",
      "file": "voice/features/2.wav",
      "from": 9.2,
      "to": 12.58
    }
  ],
  "close": [
    {
      "text": "ClaimLens. AI that shows its work.",
      "file": "voice/close/0.wav",
      "from": 0.5,
      "to": 3.04
    },
    {
      "text": "Every page read. Every rupee proved.",
      "file": "voice/close/1.wav",
      "from": 3.49,
      "to": 6.27
    },
    {
      "text": "Built by Himanshi, Chitresh and Priyanshu.",
      "file": "voice/close/2.wav",
      "from": 6.72,
      "to": 9.67
    }
  ]
};
