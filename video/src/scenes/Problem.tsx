import React from "react";
import { AbsoluteFill } from "remotion";
import { C, F } from "../theme";
import { Captions, Logo, Paper, Scene, prog, useT } from "../components/ui";

const Statement: React.FC<{ at: number; out: number; children: React.ReactNode; color?: string }> = ({ at, out, children, color = "#fbf8f1" }) => {
  const { t } = useT();
  const o = Math.min(prog(t, at, 0.45), 1 - prog(t, out, 0.35));
  return (
    <div style={{ opacity: o, transform: `translateY(${(1 - prog(t, at, 0.6)) * 26}px)`, fontFamily: F.display, fontWeight: 500,
      fontSize: 84, color, lineHeight: 1.1, textAlign: "center" }}>{children}</div>
  );
};

const PILLARS: [string, string, string][] = [
  ["Gemini reads.", "Labels files, pulls facts out of messy text, reads policy wording.", C.gBlue],
  ["Code decides.", "Fonts, hidden text, sums, dates, reused invoices, policy maths.", C.olive],
  ["Every claim is proved.", "A quote that isn't on the cited page is dropped.", C.stamp],
];

export const Problem: React.FC = () => {
  const { t } = useT();
  const dark = 1 - prog(t, 5.6, 0.6);
  const title = prog(t, 6.0, 0.7);
  return (
    <Scene bg={C.night}>
      <AbsoluteFill style={{ opacity: dark }}><Paper dark /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: 1 - dark }}><Paper /></AbsoluteFill>

      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 30, opacity: dark }}>
        <Statement at={0.2} out={5.3}>AI reads documents brilliantly.</Statement>
        <Statement at={2.0} out={5.3} color="#e8a39d">It also makes things up.</Statement>
      </AbsoluteFill>

      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: title }}>
        <div style={{ transform: `scale(${0.92 + 0.08 * title})`, display: "flex", flexDirection: "column", alignItems: "center", gap: 54, marginTop: -60 }}>
          <Logo size={150} />
          <div style={{ display: "flex", gap: 40 }}>
            {PILLARS.map(([h, s, col], i) => {
              const p = prog(t, 7.0 + i * 0.7, 0.5);
              return (
                <div key={h} style={{ width: 440, opacity: p, transform: `translateY(${(1 - p) * 30}px)`, background: C.sheet,
                  border: `1px solid ${C.rule}`, borderTop: `6px solid ${col}`, padding: "26px 28px", borderRadius: 6,
                  boxShadow: "0 16px 40px rgba(30,28,25,0.10)" }}>
                  <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 44, color: C.ink }}>{h}</div>
                  <div style={{ fontFamily: F.body, fontSize: 24, color: C.inkSoft, marginTop: 10, lineHeight: 1.35 }}>{s}</div>
                </div>
              );
            })}
          </div>
        </div>
      </AbsoluteFill>

      <Captions dark={dark > 0.5} lines={[
        { from: 0.4, to: 5.4, text: "In insurance, a made-up finding can turn down an honest family's claim." },
        { from: 6.4, to: 12.6, text: "ClaimLens flags fraud in health-insurance claims. It flags; a human decides." },
      ]} />
    </Scene>
  );
};
