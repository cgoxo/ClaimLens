import React from "react";
import { AbsoluteFill } from "remotion";
import { C, F } from "../theme";
import { cue } from "../cues";
import { Kicker, Paper, Scene, prog, useT } from "../components/ui";

// Sourced figures only; each card names its source on screen
const STATS: { phrase: string; big: string; unit: string; text: string; source: string; color: string }[] = [
  { phrase: "ten thousand crore", big: "₹8,000–10,000", unit: "crore a year", color: C.stamp,
    text: "estimated loss to health-claim fraud, waste and abuse in India", source: "BCG × Medi Assist, Nov 2025" },
  { phrase: "three crore claims", big: "3.26", unit: "crore claims", color: C.slate,
    text: "health claims processed in India in FY 2024-25", source: "IRDAI Annual Report 2024-25" },
  { phrase: "faking a bill", big: "+194%", unit: "deepfake fraud", color: C.amber,
    text: "rise in AI-powered identity fraud across Asia-Pacific in 2024", source: "Sumsub Identity Fraud Report 2024" },
];

export const Why: React.FC = () => {
  const { t } = useT();
  return (
    <Scene>
      <Paper />
      <Kicker>Why it matters</Kicker>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", gap: 40, marginTop: -40 }}>
          {STATS.map((s, i) => {
            const at = cue("why", s.phrase, 0.5 + i * 4) - 0.3;
            const p = prog(t, at, 0.6);
            return (
              <div key={s.big} style={{ width: 520, opacity: p, transform: `translateY(${(1 - p) * 40}px)`, background: C.sheet,
                border: `1px solid ${C.rule}`, borderTop: `8px solid ${s.color}`, borderRadius: 10, padding: "34px 34px 26px",
                boxShadow: "0 20px 50px rgba(30,28,25,0.12)", display: "flex", flexDirection: "column", gap: 12, minHeight: 400 }}>
                <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: s.big.length > 6 ? 62 : 104, whiteSpace: "nowrap", color: s.color, lineHeight: 1 }}>{s.big}</div>
                <div style={{ fontFamily: F.body, fontWeight: 600, fontSize: 32, color: C.ink }}>{s.unit}</div>
                <div style={{ fontFamily: F.body, fontSize: 26, color: C.inkSoft, lineHeight: 1.35, flex: 1 }}>{s.text}</div>
                <div style={{ fontFamily: F.mono, fontSize: 17, color: C.inkSoft, borderTop: `1px solid ${C.rule}`, paddingTop: 12 }}>Source: {s.source}</div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </Scene>
  );
};
