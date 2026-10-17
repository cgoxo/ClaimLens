import React from "react";
import { AbsoluteFill } from "remotion";
import { C, F } from "../theme";
import { LIVE_URL } from "../timeline";
import { cue } from "../cues";
import { Logo, Paper, Scene, prog, useT } from "../components/ui";

const TEAM = ["Himanshi", "Chitresh", "Priyanshu"];
const STACK = ["Cloud Run", "Cloud Tasks", "Firestore", "Cloud Storage", "Vertex AI Gemini", "Document AI", "Firebase Auth"];

export const Close: React.FC = () => {
  const { t } = useT();
  const a = prog(t, 0.2, 0.7);
  const b = prog(t, cue("close", "AI that shows", 1.4) - 0.2, 0.6);
  const c = prog(t, cue("close", "Every page read", 3.2) - 0.2, 0.6);
  const team = cue("close", "Built by", 6.0);
  const d = prog(t, team - 0.2, 0.6);
  return (
    <Scene bg={C.night}>
      <Paper dark />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 30, marginTop: -40 }}>
        <div style={{ opacity: a, transform: `scale(${0.94 + 0.06 * a})` }}><Logo size={160} color="#fbf8f1" /></div>
        <div style={{ opacity: b, fontFamily: F.display, fontWeight: 500, fontSize: 60, color: "#fbf8f1" }}>AI that shows its work.</div>
        <div style={{ opacity: c, fontFamily: F.display, fontWeight: 500, fontSize: 48, color: "#e8a39d" }}>Every page read. Every rupee proved.</div>

        <div style={{ opacity: d, marginTop: 26, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <div style={{ fontFamily: F.mono, fontSize: 20, letterSpacing: "0.2em", textTransform: "uppercase", color: "#bdb5a6" }}>Built by</div>
          <div style={{ display: "flex", gap: 22 }}>
            {TEAM.map((name, i) => {
              const p = prog(t, cue("close", name, team + 0.6 + i * 0.5) - 0.15, 0.4);
              return (
                <div key={name} style={{ opacity: p, transform: `translateY(${(1 - p) * 16}px)`, fontFamily: F.display, fontWeight: 600, fontSize: 46,
                  color: "#fbf8f1", padding: "10px 30px", borderRadius: 10, border: `2px solid ${[C.gBlue, C.gRed, C.gGreen][i]}` }}>{name}</div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 18, alignItems: "center", marginTop: 18 }}>
            <span style={{ fontFamily: F.mono, fontSize: 22, color: "#fbf8f1", border: "2px solid #45413a", borderRadius: 10, padding: "8px 18px" }}>{LIVE_URL}</span>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center", maxWidth: 1400 }}>
            {STACK.map((s, i) => (
              <span key={s} style={{ fontFamily: F.body, fontSize: 18, color: "#d8d0c0", padding: "6px 14px", borderRadius: 18,
                border: `1.5px solid ${[C.gBlue, C.gRed, C.gYellow, C.gGreen][i % 4]}` }}>{s}</span>
            ))}
          </div>
        </div>
      </AbsoluteFill>
    </Scene>
  );
};
