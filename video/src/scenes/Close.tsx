import React from "react";
import { AbsoluteFill } from "remotion";
import { C, F } from "../theme";
import { LIVE_URL } from "../timeline";
import { Logo, Paper, Scene, prog, useT } from "../components/ui";

const STACK = ["Cloud Run", "Cloud Tasks", "Firestore", "Cloud Storage", "Vertex AI Gemini", "Document AI", "Firebase Auth"];

export const Close: React.FC = () => {
  const { t } = useT();
  const a = prog(t, 0.2, 0.7), b = prog(t, 1.4, 0.6), c = prog(t, 2.4, 0.6), d = prog(t, 3.4, 0.6);
  return (
    <Scene bg={C.night}>
      <Paper dark />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 40 }}>
        <div style={{ opacity: a, transform: `scale(${0.94 + 0.06 * a})` }}><Logo size={170} color="#fbf8f1" /></div>
        <div style={{ opacity: b, fontFamily: F.display, fontWeight: 500, fontSize: 64, color: "#fbf8f1" }}>
          It flags. <span style={{ color: "#e8a39d" }}>A human decides.</span>
        </div>
        <div style={{ opacity: c, fontFamily: F.mono, fontSize: 30, color: "#fbf8f1", border: "2px solid #45413a", borderRadius: 10, padding: "14px 26px" }}>
          {LIVE_URL}
        </div>
        <div style={{ opacity: d, display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center", maxWidth: 1400 }}>
          {STACK.map((s, i) => (
            <span key={s} style={{ fontFamily: F.body, fontSize: 22, color: "#d8d0c0", padding: "8px 16px", borderRadius: 20,
              border: `1.5px solid ${[C.gBlue, C.gRed, C.gYellow, C.gGreen][i % 4]}` }}>{s}</span>
          ))}
        </div>
      </AbsoluteFill>
    </Scene>
  );
};
