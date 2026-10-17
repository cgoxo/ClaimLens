// Written by voice.mjs: every narration line, its clip and when it plays (seconds from the scene's start)
export type VoiceLine = { text: string; file: string; from: number; to: number };
export const VOICE_LINES: Record<string, VoiceLine[]> = {
  "hook": [
    {
      "text": "This is a hospital bill.",
      "file": "voice/hook/0.wav",
      "from": 0.5,
      "to": 1.72
    },
    {
      "text": "Someone hid the real total under a white box,",
      "file": "voice/hook/1.wav",
      "from": 2.3,
      "to": 4.92
    },
    {
      "text": "and typed a bigger one on top, in a different font.",
      "file": "voice/hook/2.wav",
      "from": 5.24,
      "to": 8.03
    },
    {
      "text": "Would a reviewer catch it? Would an AI?",
      "file": "voice/hook/3.wav",
      "from": 8.35,
      "to": 10.58
    }
  ],
  "problem": [
    {
      "text": "AI reads documents brilliantly. It also makes things up.",
      "file": "voice/problem/0.wav",
      "from": 0.45,
      "to": 3.98
    },
    {
      "text": "In insurance, that hurts honest families.",
      "file": "voice/problem/1.wav",
      "from": 4.3,
      "to": 6.6
    },
    {
      "text": "So we built ClaimLens.",
      "file": "voice/problem/2.wav",
      "from": 6.92,
      "to": 8.36
    },
    {
      "text": "Gemini reads. Code decides. Every claim is proved.",
      "file": "voice/problem/3.wav",
      "from": 8.68,
      "to": 12.33
    }
  ],
  "upload": [
    {
      "text": "A reviewer signs in with Google, through Firebase.",
      "file": "voice/upload/0.wav",
      "from": 0.45,
      "to": 3.03
    },
    {
      "text": "They upload the claim and its policy. Here, our sample claim.",
      "file": "voice/upload/1.wav",
      "from": 3.6,
      "to": 7.28
    },
    {
      "text": "The case goes onto a Cloud Tasks queue, and runs in the background.",
      "file": "voice/upload/2.wav",
      "from": 9.1,
      "to": 12.75
    },
    {
      "text": "Every page is read. Photos go through Document AI.",
      "file": "voice/upload/3.wav",
      "from": 14,
      "to": 17.49
    },
    {
      "text": "Gemini pulls out the facts.",
      "file": "voice/upload/4.wav",
      "from": 17.81,
      "to": 19.46
    },
    {
      "text": "In under a minute, the case is ready.",
      "file": "voice/upload/5.wav",
      "from": 19.78,
      "to": 21.54
    }
  ],
  "results": [
    {
      "text": "Risk: one hundred out of one hundred. Investigate.",
      "file": "voice/results/0.wav",
      "from": 0.45,
      "to": 3.46
    },
    {
      "text": "Gemini writes the summary, but plain code sets the score.",
      "file": "voice/results/1.wav",
      "from": 5,
      "to": 8.53
    },
    {
      "text": "Every finding is marked on its own page.",
      "file": "voice/results/2.wav",
      "from": 9.2,
      "to": 11.45
    },
    {
      "text": "This total's font doesn't match any other amount.",
      "file": "voice/results/3.wav",
      "from": 11.77,
      "to": 14.58
    },
    {
      "text": "This pharmacy invoice was already used in another claim, even on a photo.",
      "file": "voice/results/4.wav",
      "from": 15.7,
      "to": 19.84
    },
    {
      "text": "The policy becomes a rulebook. Cataract is still in its waiting period.",
      "file": "voice/results/5.wav",
      "from": 21.7,
      "to": 25.89
    },
    {
      "text": "So the settlement, worked out line by line in code, is zero.",
      "file": "voice/results/6.wav",
      "from": 27.2,
      "to": 30.87
    }
  ],
  "proof": [
    {
      "text": "This is what makes it trustworthy.",
      "file": "voice/proof/0.wav",
      "from": 0.45,
      "to": 2.21
    },
    {
      "text": "Every fact Gemini returns must quote its page.",
      "file": "voice/proof/1.wav",
      "from": 2.53,
      "to": 5.39
    },
    {
      "text": "Code looks for that quote. If it isn't there, it's dropped.",
      "file": "voice/proof/2.wav",
      "from": 5.71,
      "to": 9.3
    },
    {
      "text": "Typos are fine. A different number, or a missing not, never is.",
      "file": "voice/proof/3.wav",
      "from": 9.8,
      "to": 13.75
    }
  ],
  "agent": [
    {
      "text": "On a finished case, the reviewer can question a Gemini agent.",
      "file": "voice/agent/0.wav",
      "from": 0.45,
      "to": 3.97
    },
    {
      "text": "It calls read-only tools over the case.",
      "file": "voice/agent/1.wav",
      "from": 4.3,
      "to": 6.64
    },
    {
      "text": "And its answers pass the same proof gate.",
      "file": "voice/agent/2.wav",
      "from": 7.6,
      "to": 10.14
    },
    {
      "text": "Draw a box on any page, and ask about just that area.",
      "file": "voice/agent/3.wav",
      "from": 13.1,
      "to": 16.36
    },
    {
      "text": "It adds up the lines itself. The total doesn't fit.",
      "file": "voice/agent/4.wav",
      "from": 17.2,
      "to": 20.29
    },
    {
      "text": "It can suggest a change, but only as a proposal.",
      "file": "voice/agent/5.wav",
      "from": 23.2,
      "to": 26.24
    },
    {
      "text": "The agent investigates. Code verifies. A human decides.",
      "file": "voice/agent/6.wav",
      "from": 28.2,
      "to": 32.08
    }
  ],
  "cloud": [
    {
      "text": "It all runs on Google Cloud. Firebase signs reviewers in.",
      "file": "voice/cloud/0.wav",
      "from": 0.5,
      "to": 4.09
    },
    {
      "text": "One Cloud Run service runs the app, the API and the agent.",
      "file": "voice/cloud/1.wav",
      "from": 4.41,
      "to": 8.17
    },
    {
      "text": "Files go to Cloud Storage, cases to Firestore.",
      "file": "voice/cloud/2.wav",
      "from": 8.49,
      "to": 11.82
    },
    {
      "text": "Cloud Tasks runs each analysis, retried if it fails, never twice.",
      "file": "voice/cloud/3.wav",
      "from": 12.3,
      "to": 16.84
    },
    {
      "text": "Document AI reads the scans. Gemini on Vertex AI reads the meaning.",
      "file": "voice/cloud/4.wav",
      "from": 17.3,
      "to": 21.88
    },
    {
      "text": "Every push is tested and deployed automatically, with no stored keys.",
      "file": "voice/cloud/5.wav",
      "from": 22.2,
      "to": 26.18
    }
  ],
  "engineering": [
    {
      "text": "More than six hundred automated tests run before anything ships.",
      "file": "voice/engineering/0.wav",
      "from": 0.5,
      "to": 4.12
    },
    {
      "text": "And we measure. A forgery model that couldn't beat a coin flip on our photos?",
      "file": "voice/engineering/1.wav",
      "from": 6.9,
      "to": 11.37
    },
    {
      "text": "We cut it.",
      "file": "voice/engineering/2.wav",
      "from": 11.69,
      "to": 12.34
    }
  ],
  "close": [
    {
      "text": "ClaimLens.",
      "file": "voice/close/0.wav",
      "from": 0.6,
      "to": 1.24
    },
    {
      "text": "It flags. A human decides.",
      "file": "voice/close/1.wav",
      "from": 1.6,
      "to": 3.53
    }
  ]
};
