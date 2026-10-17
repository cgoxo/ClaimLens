import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { C, F } from "../theme";
import { Captions, Kicker, Paper, Scene, Stamp, ease, prog, useT } from "../components/ui";

const PAGE = [
  "Hospital Bill - Invoice INV-SEH-2026-0412",
  "Patient: Rahul Verma    Bill date: 13-Mar-2026",
  "Room charges (3 days x Rs 4,500)    Rs 13,500",
  "Surgeon and OT charges    Rs 22,000",
  "Intraocular lens (IOL)    Rs 8,000",
  "Consumables    Rs 2,000",
  "TOTAL    Rs 48,500",
];

// quote -> the page line it matches, or null when it isn't on the page
const QUOTES: { text: string; line: number | null; at: number }[] = [
  { text: "Invoice INV-SEH-2026-0412", line: 0, at: 1.2 },
  { text: "TOTAL Rs 48,500", line: 6, at: 3.2 },
  { text: "Discount Rs 5,000", line: null, at: 5.4 },
];

export const ProofGate: React.FC = () => {
  const { t } = useT();
  const rules = prog(t, 9.6, 0.6);
  return (
    <Scene>
      <Paper />
      <Kicker>The proof gate · pipeline/prove.py</Kicker>

      {/* Gemini */}
      <div style={{ position: "absolute", left: 130, top: 300, width: 420 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: F.body, fontWeight: 600, fontSize: 32, color: C.ink, opacity: prog(t, 0.2) }}>
          <div style={{ width: 46, height: 46, borderRadius: 23, background: `conic-gradient(${C.gBlue}, ${C.gRed}, ${C.gYellow}, ${C.gGreen}, ${C.gBlue})` }} />
          Gemini 2.5 Flash says…
        </div>
        <div style={{ fontFamily: F.body, fontSize: 22, color: C.inkSoft, marginTop: 8, opacity: prog(t, 0.4) }}>each fact comes with a quote and a page</div>
      </div>

      {QUOTES.map((q, i) => {
        const shown = prog(t, q.at - 0.4, 0.4);
        const y = 430 + i * 110;
        const ok = q.line !== null;
        const reach = interpolate(t, [q.at, q.at + 0.9], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
        const verdict = t > q.at + 1.0;
        const color = !verdict ? C.slate : ok ? C.olive : C.stamp;
        const x1 = 690, y1 = y + 30, x2 = 1086, y2 = ok ? 288 + (q.line ?? 0) * 45 + ((q.line ?? 0) >= 6 ? 18 : 0) : 520;
        const back = ok ? 0 : prog(t, q.at + 1.6, 0.6);
        const len = reach * (1 - back);
        return (
          <React.Fragment key={q.text}>
            <svg style={{ position: "absolute", inset: 0 }} width={1920} height={1080}>
              <line x1={x1} y1={y1} x2={x1 + (x2 - x1) * len} y2={y1 + (y2 - y1) * len} stroke={color} strokeWidth={4}
                strokeDasharray={ok ? "none" : "10 8"} opacity={shown} />
            </svg>
            <div style={{ position: "absolute", left: 130, top: y, width: 560, opacity: shown * (verdict && !ok ? 1 - prog(t, q.at + 2.4, 0.6) * 0.5 : 1),
              fontFamily: F.mono, fontSize: 26, padding: "12px 18px", background: C.sheet, border: `3px solid ${color}`, borderRadius: 8,
              boxShadow: "0 10px 24px rgba(30,28,25,0.12)", color: C.ink, whiteSpace: "nowrap", display: "flex", justifyContent: "space-between" }}>
              <span style={{ textDecoration: verdict && !ok ? "line-through" : "none" }}>“{q.text}”</span>
              {verdict && <span style={{ fontFamily: F.body, fontWeight: 600, color }}>{ok ? "✓ p.3" : "✗ not on p.3"}</span>}
            </div>
          </React.Fragment>
        );
      })}

      {/* The page */}
      <div style={{ position: "absolute", right: 130, top: 180, width: 700, height: 560, background: "white", padding: "44px 48px",
        boxShadow: "0 30px 60px rgba(30,28,25,0.16)", fontFamily: "Helvetica, Arial, sans-serif", opacity: prog(t, 0.3, 0.6) }}>
        <div style={{ fontFamily: F.mono, fontSize: 18, color: C.inkSoft, marginBottom: 18 }}>claim · page 3</div>
        {PAGE.map((l, i) => {
          const hit = QUOTES.find((q) => q.line === i && t > q.at + 1.0);
          return (
            <div key={i} style={{ fontSize: i === 0 ? 24 : 21, fontWeight: i === 0 || i === 6 ? 700 : 400, color: "#111", padding: "7px 8px", marginBottom: i === 5 ? 18 : 6,
              background: hit ? "rgba(79,107,46,0.16)" : "transparent", outline: hit ? `3px solid ${C.olive}` : "none", borderRadius: 4 }}>{l}</div>
          );
        })}
      </div>

      <div style={{ position: "absolute", left: 560, top: 640 }}>
        <Stamp text="DROPPED" sub="no proof, no finding" at={6.8} size={48} />
      </div>

      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 160, opacity: rules }}>
        <div style={{ display: "flex", gap: 22 }}>
          {[
            ["Fuzzy match ≥ 90", "≥ 80 on OCR"],
            ["Numbers must agree", "₹5,000 ≠ ₹50,000"],
            ["Negations must agree", "covered ≠ not covered"],
          ].map(([a, b]) => (
            <div key={a} style={{ background: C.ink, color: "#fbf8f1", padding: "14px 22px", borderRadius: 8, fontFamily: F.body, fontSize: 24 }}>
              <b>{a}</b> <span style={{ opacity: 0.75 }}>· {b}</span>
            </div>
          ))}
        </div>
      </AbsoluteFill>

      <Captions lines={[
        { from: 0.4, to: 5.0, text: "Gemini only reads. Every fact and finding it returns must quote the page it came from." },
        { from: 5.1, to: 9.6, text: "Code looks for that quote on that page. If it isn't there, the claim is dropped." },
        { from: 9.7, to: 14.7, text: "Typos from OCR are allowed. A different number, or a missing “not”, never is." },
      ]} />
    </Scene>
  );
};
