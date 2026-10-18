// Written by voice-recorded.mjs from the team's recordings: every narration line, its clip and when it plays
export type VoiceLine = { text: string; file: string; from: number; to: number };
export const VOICE_LINES: Record<string, VoiceLine[]> = {
  "hook": [
    {
      "text": "Look at this hospital bill.",
      "file": "voice/hook/0.wav",
      "from": 0.5,
      "to": 2.16
    },
    {
      "text": "The real total is hidden under a white box, and a bigger one is typed on top.",
      "file": "voice/hook/1.wav",
      "from": 2.61,
      "to": 8.39
    },
    {
      "text": "Would your team catch it?",
      "file": "voice/hook/2.wav",
      "from": 8.84,
      "to": 10.48
    }
  ],
  "why": [
    {
      "text": "In India alone, health insurers lose up to ten thousand crore rupees a year to fraud, waste and abuse.",
      "file": "voice/why/0.wav",
      "from": 0.45,
      "to": 9.25
    },
    {
      "text": "That's across more than three crore claims a year.",
      "file": "voice/why/1.wav",
      "from": 9.7,
      "to": 13.8
    },
    {
      "text": "And with AI, faking a bill gets easier every day.",
      "file": "voice/why/2.wav",
      "from": 14.25,
      "to": 18.03
    }
  ],
  "problem": [
    {
      "text": "Across Asia-Pacific, claims arrive as PDFs, scans and phone photos.",
      "file": "voice/problem/0.wav",
      "from": 0.45,
      "to": 5.95
    },
    {
      "text": "No reviewer can check every page.",
      "file": "voice/problem/1.wav",
      "from": 6.4,
      "to": 9.22
    },
    {
      "text": "So we built ClaimLens.",
      "file": "voice/problem/2.wav",
      "from": 9.67,
      "to": 11.75
    },
    {
      "text": "Gemini reads. Code decides. Every claim is proved.",
      "file": "voice/problem/3.wav",
      "from": 12.2,
      "to": 16.46
    }
  ],
  "upload": [
    {
      "text": "Sign in with Google, and drop in the claim and the policy.",
      "file": "voice/upload/0.wav",
      "from": 0.45,
      "to": 4.51
    },
    {
      "text": "ClaimLens reads every page, and runs OCR on photos with Document AI.",
      "file": "voice/upload/1.wav",
      "from": 9.1,
      "to": 14.76
    },
    {
      "text": "It confirms these are real insurance documents, then Gemini extracts the facts.",
      "file": "voice/upload/2.wav",
      "from": 15.21,
      "to": 20.97
    },
    {
      "text": "In under a minute, the case file is ready.",
      "file": "voice/upload/3.wav",
      "from": 21.42,
      "to": 24
    }
  ],
  "results": [
    {
      "text": "Risk: one hundred out of one hundred. Recommendation: investigate.",
      "file": "voice/results/0.wav",
      "from": 0.45,
      "to": 5.43
    },
    {
      "text": "Every fact links back to the page it came from.",
      "file": "voice/results/1.wav",
      "from": 5.88,
      "to": 9.86
    },
    {
      "text": "Every problem is marked on the document: an amount in a different font, the real total hidden underneath,",
      "file": "voice/results/2.wav",
      "from": 10.31,
      "to": 18.25
    },
    {
      "text": "an invoice already used in another claim, even on a phone photo.",
      "file": "voice/results/3.wav",
      "from": 18.7,
      "to": 23.86
    },
    {
      "text": "The policy becomes a rulebook. A waiting period applies, line by line.",
      "file": "voice/results/4.wav",
      "from": 24.31,
      "to": 29.79
    },
    {
      "text": "Payable: zero.",
      "file": "voice/results/5.wav",
      "from": 30.24,
      "to": 31.38
    }
  ],
  "proof": [
    {
      "text": "AI can make things up. So every fact must quote its page.",
      "file": "voice/proof/0.wav",
      "from": 0.45,
      "to": 5.57
    },
    {
      "text": "No quote, no finding.",
      "file": "voice/proof/1.wav",
      "from": 6.02,
      "to": 8.2
    },
    {
      "text": "A different number, or a missing \"not\", never passes.",
      "file": "voice/proof/2.wav",
      "from": 9.8,
      "to": 13.94
    }
  ],
  "agent": [
    {
      "text": "And this is where it becomes agentic.",
      "file": "voice/agent/0.wav",
      "from": 0.45,
      "to": 2.91
    },
    {
      "text": "Reviewers question a Gemini agent that investigates the case with its own tools.",
      "file": "voice/agent/1.wav",
      "from": 3.36,
      "to": 9.18
    },
    {
      "text": "Every answer is checked against the documents.",
      "file": "voice/agent/2.wav",
      "from": 9.63,
      "to": 13.47
    },
    {
      "text": "Draw a box on any page, and ask about just that area.",
      "file": "voice/agent/3.wav",
      "from": 14.1,
      "to": 18.78
    },
    {
      "text": "It does the maths, and spots the total that doesn't fit.",
      "file": "voice/agent/4.wav",
      "from": 19.23,
      "to": 23.47
    },
    {
      "text": "It even proposes changes, but nothing happens until a human approves.",
      "file": "voice/agent/5.wav",
      "from": 24.2,
      "to": 29.42
    },
    {
      "text": "The agent investigates. Code verifies. A human decides.",
      "file": "voice/agent/6.wav",
      "from": 29.87,
      "to": 35.85
    }
  ],
  "cloud": [
    {
      "text": "ClaimLens runs entirely on Google Cloud, in the Mumbai region.",
      "file": "voice/cloud/0.wav",
      "from": 0.45,
      "to": 4.65
    },
    {
      "text": "Firebase signs reviewers in.",
      "file": "voice/cloud/1.wav",
      "from": 5.1,
      "to": 7.54
    },
    {
      "text": "One Cloud Run service hosts the app, the pipeline and the agent, and scales to zero when idle.",
      "file": "voice/cloud/2.wav",
      "from": 7.99,
      "to": 16.49
    },
    {
      "text": "Cloud Tasks runs every analysis reliably. Firestore and Cloud Storage keep the case file.",
      "file": "voice/cloud/3.wav",
      "from": 16.94,
      "to": 24.74
    },
    {
      "text": "Document AI reads the scans. Gemini on Vertex AI reads the meaning.",
      "file": "voice/cloud/4.wav",
      "from": 25.19,
      "to": 31.29
    },
    {
      "text": "Every release ships automatically, with no stored keys.",
      "file": "voice/cloud/5.wav",
      "from": 31.74,
      "to": 36.54
    }
  ],
  "features": [
    {
      "text": "Edited files. Hidden text. Totals that don't add up.",
      "file": "voice/features/0.wav",
      "from": 0.45,
      "to": 5.29
    },
    {
      "text": "Reused invoices. Missing pages. Policy limits.",
      "file": "voice/features/1.wav",
      "from": 5.74,
      "to": 9.78
    },
    {
      "text": "One case file. Every problem, on its page.",
      "file": "voice/features/2.wav",
      "from": 10.23,
      "to": 13.99
    }
  ],
  "close": [
    {
      "text": "ClaimLens. AI that shows its work.",
      "file": "voice/close/0.wav",
      "from": 0.5,
      "to": 4.1
    },
    {
      "text": "Every page read. Every rupee proved.",
      "file": "voice/close/1.wav",
      "from": 4.55,
      "to": 7.81
    },
    {
      "text": "Built by Himanshi, Chitresh and Priyanshu.",
      "file": "voice/close/2.wav",
      "from": 8.26,
      "to": 11.5
    }
  ]
};
