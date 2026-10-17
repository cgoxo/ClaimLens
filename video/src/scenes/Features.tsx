import React from "react";
import { AbsoluteFill } from "remotion";
import { C, F } from "../theme";
import { cue } from "../cues";
import { Kicker, Paper, Scene, prog, useT } from "../components/ui";

// Everything ClaimLens checks and does, grouped; each group appears as the narration names it
const GROUPS: { title: string; color: string; phrase: string; items: string[] }[] = [
  { title: "Edited documents", color: C.stamp, phrase: "Edited files",
    items: ["Amounts in a different font", "Text hidden under white boxes", "Editing-tool traces", "Files changed after creation", "OCR layer that doesn't match the image"] },
  { title: "Stories that don't add up", color: C.amber, phrase: "Totals",
    items: ["Bills that don't sum", "Impossible date order", "Name and policy-number mismatches", "Room days longer than the stay", "Double charges"] },
  { title: "Across claims", color: C.slate, phrase: "Reused invoices",
    items: ["Invoices reused in other claims", "The same page uploaded twice", "Missing pages in a bill"] },
  { title: "Policy and payout", color: C.olive, phrase: "Policy limits",
    items: ["Waiting periods", "Room-rent and ICU limits", "Non-payable items", "Line-by-line settlement", "Investigate, query or approve"] },
  { title: "For the reviewer", color: C.gBlue, phrase: "One case file",
    items: ["Every finding on its page", "Accept or dismiss, with history", "Ask the Gemini agent", "Notified when ready"] },
];

export const Features: React.FC = () => {
  const { t } = useT();
  const last = cue("features", "One case file", 9);
  const banner = prog(t, cue("features", "Every problem", last + 1.2), 0.5);
  return (
    <Scene>
      <Paper />
      <Kicker>Everything it catches</Kicker>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 320px)", gap: 22, marginTop: -70, alignItems: "start" }}>
          {GROUPS.map((g, gi) => {
            const at = cue("features", g.phrase, 0.5 + gi * 2.2) - 0.25;
            const p = prog(t, at, 0.5);
            return (
              <div key={g.title} style={{ opacity: p, transform: `translateY(${(1 - p) * 30}px)`, background: C.sheet, border: `1px solid ${C.rule}`,
                borderTop: `7px solid ${g.color}`, borderRadius: 10, padding: "20px 20px 14px", boxShadow: "0 16px 36px rgba(30,28,25,0.10)" }}>
                <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 30, color: C.ink, marginBottom: 12, lineHeight: 1.1 }}>{g.title}</div>
                {g.items.map((item, i) => {
                  const q = prog(t, at + 0.2 + i * 0.12, 0.3);
                  return (
                    <div key={item} style={{ opacity: q, display: "flex", gap: 10, alignItems: "baseline", fontFamily: F.body, fontSize: 21,
                      color: C.ink, padding: "7px 0", borderTop: i ? `1px solid ${C.rule}` : "none" }}>
                      <span style={{ color: g.color, fontWeight: 700 }}>✓</span>{item}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 150, textAlign: "center", opacity: banner,
        fontFamily: F.display, fontWeight: 600, fontSize: 54, color: C.ink, transform: `translateY(${(1 - banner) * 20}px)` }}>
        One case file. <span style={{ color: C.stamp }}>Every problem, on its page.</span>
      </div>
    </Scene>
  );
};
