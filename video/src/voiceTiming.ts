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
      "text": "The real total is hidden under a white box,",
      "file": "voice/hook/1.wav",
      "from": 2.67,
      "to": 5.44
    },
    {
      "text": "and a bigger one is typed on top.",
      "file": "voice/hook/2.wav",
      "from": 5.99,
      "to": 8.1
    },
    {
      "text": "Would you catch it?",
      "file": "voice/hook/3.wav",
      "from": 8.65,
      "to": 9.48
    }
  ],
  "problem": [
    {
      "text": "AI reads documents brilliantly.",
      "file": "voice/problem/0.wav",
      "from": 0.45,
      "to": 2.51
    },
    {
      "text": "But it also makes things up.",
      "file": "voice/problem/1.wav",
      "from": 3.06,
      "to": 4.85
    },
    {
      "text": "So we built ClaimLens.",
      "file": "voice/problem/2.wav",
      "from": 6,
      "to": 7.61
    },
    {
      "text": "Gemini reads. Code decides. Every claim is proved.",
      "file": "voice/problem/3.wav",
      "from": 8.16,
      "to": 12.29
    }
  ],
  "upload": [
    {
      "text": "A reviewer signs in with Google,",
      "file": "voice/upload/0.wav",
      "from": 0.45,
      "to": 2.46
    },
    {
      "text": "and uploads the claim and the policy.",
      "file": "voice/upload/1.wav",
      "from": 3.6,
      "to": 5.85
    },
    {
      "text": "Cloud Tasks runs the analysis in the background.",
      "file": "voice/upload/2.wav",
      "from": 9.1,
      "to": 12.12
    },
    {
      "text": "Every page is read, and Gemini pulls out the facts.",
      "file": "voice/upload/3.wav",
      "from": 14,
      "to": 17.42
    },
    {
      "text": "In under a minute, it's ready.",
      "file": "voice/upload/4.wav",
      "from": 19,
      "to": 20.43
    }
  ],
  "results": [
    {
      "text": "Risk: one hundred out of one hundred.",
      "file": "voice/results/0.wav",
      "from": 0.45,
      "to": 2.55
    },
    {
      "text": "Gemini writes the summary. Code sets the score.",
      "file": "voice/results/1.wav",
      "from": 5,
      "to": 8.56
    },
    {
      "text": "Every finding is marked on its page.",
      "file": "voice/results/2.wav",
      "from": 9.2,
      "to": 11.41
    },
    {
      "text": "This total uses a different font.",
      "file": "voice/results/3.wav",
      "from": 11.96,
      "to": 14.11
    },
    {
      "text": "This invoice was already used in another claim.",
      "file": "voice/results/4.wav",
      "from": 15.7,
      "to": 18.54
    },
    {
      "text": "And cataract is still in its waiting period,",
      "file": "voice/results/5.wav",
      "from": 21.7,
      "to": 24.5
    },
    {
      "text": "so the payable amount is zero.",
      "file": "voice/results/6.wav",
      "from": 27.2,
      "to": 29.23
    }
  ],
  "proof": [
    {
      "text": "Here's why you can trust it.",
      "file": "voice/proof/0.wav",
      "from": 0.45,
      "to": 2.07
    },
    {
      "text": "Every fact must quote its page.",
      "file": "voice/proof/1.wav",
      "from": 2.62,
      "to": 4.76
    },
    {
      "text": "If the quote isn't there, it's dropped.",
      "file": "voice/proof/2.wav",
      "from": 5.4,
      "to": 7.66
    },
    {
      "text": "A different number, or a missing \"not\", never passes.",
      "file": "voice/proof/3.wav",
      "from": 9.8,
      "to": 13.14
    }
  ],
  "agent": [
    {
      "text": "Now, the agent.",
      "file": "voice/agent/0.wav",
      "from": 0.45,
      "to": 1.89
    },
    {
      "text": "Reviewers can question Gemini about the case.",
      "file": "voice/agent/1.wav",
      "from": 2.44,
      "to": 5.2
    },
    {
      "text": "It uses read-only tools,",
      "file": "voice/agent/2.wav",
      "from": 5.75,
      "to": 7.44
    },
    {
      "text": "and every answer passes the same proof check.",
      "file": "voice/agent/3.wav",
      "from": 7.99,
      "to": 10.96
    },
    {
      "text": "Draw a box on the bill, and ask about just that area.",
      "file": "voice/agent/4.wav",
      "from": 13.1,
      "to": 16.54
    },
    {
      "text": "It adds up the lines, and the total doesn't fit.",
      "file": "voice/agent/5.wav",
      "from": 17.2,
      "to": 19.94
    },
    {
      "text": "It can suggest changes, but only a human can apply them.",
      "file": "voice/agent/6.wav",
      "from": 23.2,
      "to": 27.02
    },
    {
      "text": "The agent investigates. Code verifies. A human decides.",
      "file": "voice/agent/7.wav",
      "from": 28.3,
      "to": 32.69
    }
  ],
  "cloud": [
    {
      "text": "All of it runs on Google Cloud.",
      "file": "voice/cloud/0.wav",
      "from": 0.5,
      "to": 2.4
    },
    {
      "text": "One Cloud Run service hosts everything.",
      "file": "voice/cloud/1.wav",
      "from": 4.3,
      "to": 6.96
    },
    {
      "text": "Files in Cloud Storage. Cases in Firestore.",
      "file": "voice/cloud/2.wav",
      "from": 8.3,
      "to": 11.84
    },
    {
      "text": "Cloud Tasks retries failures, and never runs a job twice.",
      "file": "voice/cloud/3.wav",
      "from": 12.39,
      "to": 16.38
    },
    {
      "text": "Document AI reads the scans. Gemini, on Vertex AI, reads the meaning.",
      "file": "voice/cloud/4.wav",
      "from": 17.3,
      "to": 22.68
    },
    {
      "text": "And every push is tested and deployed automatically.",
      "file": "voice/cloud/5.wav",
      "from": 23.23,
      "to": 26.37
    }
  ],
  "engineering": [
    {
      "text": "Over six hundred tests run before anything ships.",
      "file": "voice/engineering/0.wav",
      "from": 0.5,
      "to": 3.81
    },
    {
      "text": "And when a forgery model failed our tests, we cut it.",
      "file": "voice/engineering/1.wav",
      "from": 6.9,
      "to": 10.53
    }
  ],
  "close": [
    {
      "text": "ClaimLens.",
      "file": "voice/close/0.wav",
      "from": 0.6,
      "to": 1.31
    },
    {
      "text": "It flags. A human decides.",
      "file": "voice/close/1.wav",
      "from": 1.86,
      "to": 4.03
    }
  ]
};
