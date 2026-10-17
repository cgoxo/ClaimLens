import React from "react";
import { C, F } from "../theme";
import { Captions, Kicker, Paper, Scene, prog, useT } from "../components/ui";

// Counted from the repo (test functions in backend/tests, it()/test() calls in frontend/src) and docs/eval
const COUNTERS: [number, string, string][] = [
  [465, "+", "backend tests"],
  [151, "+", "frontend tests"],
  [4, "/4", "live test claims scored exactly as expected"],
];

const FACTS: [string, string][] = [
  ["Measured, not guessed", "CAT-Net forgery model scored AUC 0.40 on our photos, so we dropped it"],
  ["Runs exactly once", "a Firestore transaction claims each job; duplicates are skipped"],
  ["Local = cloud", "every Google service sits behind an interface with a local stand-in"],
  ["Private by default", "a case is visible only to its owner; others get 404"],
];

export const Engineering: React.FC = () => {
  const { t } = useT();
  return (
    <Scene>
      <Paper />
      <Kicker>Engineered, and measured</Kicker>
      <div style={{ position: "absolute", top: 150, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 70 }}>
        {COUNTERS.map(([n, suffix, label], i) => {
          const p = prog(t, 0.4 + i * 0.35, 1.4);
          return (
            <div key={label} style={{ width: 460, textAlign: "center", opacity: prog(t, 0.4 + i * 0.35, 0.4) }}>
              <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 150, color: C.ink, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
                {Math.round(n * p)}<span style={{ color: C.stamp }}>{suffix}</span>
              </div>
              <div style={{ fontFamily: F.body, fontSize: 28, color: C.inkSoft, marginTop: 10 }}>{label}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", top: 520, left: 170, right: 170, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
        {FACTS.map(([a, b], i) => {
          const p = prog(t, 3.2 + i * 0.5, 0.5);
          return (
            <div key={a} style={{ opacity: p, transform: `translateY(${(1 - p) * 22}px)`, background: C.sheet, border: `1px solid ${C.rule}`,
              borderLeft: `8px solid ${[C.stamp, C.gBlue, C.olive, C.amber][i]}`, borderRadius: 8, padding: "20px 26px" }}>
              <div style={{ fontFamily: F.body, fontWeight: 600, fontSize: 30, color: C.ink }}>{a}</div>
              <div style={{ fontFamily: F.body, fontSize: 23, color: C.inkSoft, marginTop: 6 }}>{b}</div>
            </div>
          );
        })}
      </div>
      <Captions lines={[
        { from: 0.4, to: 6.8, text: "Over six hundred automated tests run on every push, before anything deploys." },
        { from: 6.9, to: 13.7, text: "And we measure: a forgery model that couldn't beat a coin flip on photos was cut." },
      ]} />
    </Scene>
  );
};
