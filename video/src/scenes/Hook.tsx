import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { C, F } from "../theme";
import { Captions, Paper, Scene, ease, prog, useT } from "../components/ui";

// The forgery in the sample claim, rebuilt: a white box hides the real total and a new one is typed on top
const ITEMS: [string, string][] = [
  ["Room charges (3 days x Rs 4,500)", "Rs 13,500"],
  ["Surgeon and OT charges", "Rs 22,000"],
  ["Intraocular lens (IOL)", "Rs 8,000"],
  ["Consumables", "Rs 2,000"],
];

export const Hook: React.FC = () => {
  const { t } = useT();
  const zoom = interpolate(t, [5.6, 7.2], [1, 1.45], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const pan = interpolate(t, [5.6, 7.2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const box = prog(t, 2.4, 0.5);
  const typed = Math.floor(interpolate(t, [3.3, 4.2], [0, 9], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const fakeTotal = "Rs 48,500".slice(0, typed);
  const notes = prog(t, 7.4, 0.5);
  const fadeAll = 1 - prog(t, 10.6, 0.8);

  return (
    <Scene>
      <Paper />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: fadeAll }}>
        <div style={{ transform: `scale(${zoom}) translate(${pan * -250}px, ${pan * -60}px)`, transformOrigin: "center" }}>
          <div style={{
            width: 760, padding: "56px 64px", background: "white", boxShadow: "0 30px 60px rgba(30,28,25,0.18)",
            fontFamily: "Helvetica, Arial, sans-serif", color: "#111", opacity: prog(t, 0, 0.6), transform: `translateY(${(1 - prog(t, 0, 0.8)) * 30}px)`,
          }}>
            <div style={{ fontWeight: 700, fontSize: 30 }}>Hospital Bill - Invoice INV-SEH-2026-0412</div>
            <div style={{ fontSize: 18, marginTop: 14, color: "#333" }}>Patient: Rahul Verma &nbsp;&nbsp;&nbsp; Bill date: 13-Mar-2026</div>
            <div style={{ marginTop: 34, display: "grid", gridTemplateColumns: "1fr auto", rowGap: 12, fontSize: 21 }}>
              {ITEMS.map(([d, a]) => (
                <React.Fragment key={d}><span>{d}</span><span style={{ textAlign: "right" }}>{a}</span></React.Fragment>
              ))}
            </div>
            <div style={{ marginTop: 36, display: "grid", gridTemplateColumns: "1fr auto", fontSize: 23, fontWeight: 700, position: "relative" }}>
              <span>TOTAL</span>
              <span style={{ position: "relative", minWidth: 150, textAlign: "right" }}>
                <span>Rs 45,500</span>
                {/* the white box */}
                <span style={{ position: "absolute", right: -8, top: -6, bottom: -6, width: `${box * 170}px`, background: "white",
                  boxShadow: box > 0 && box < 1 ? "0 0 0 1px #ddd" : "none" }} />
                <span style={{ position: "absolute", right: 0, top: 1, fontFamily: "'Times New Roman', Times, serif", fontWeight: 400, fontSize: 24 }}>{fakeTotal}</span>
              </span>
            </div>
          </div>
        </div>
      </AbsoluteFill>

      {/* annotations once zoomed in */}
      <div style={{ position: "absolute", top: 430, right: 90, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 18, opacity: notes * fadeAll, transform: `translateX(${(1 - notes) * 30}px)` }}>
        <div style={{ fontFamily: F.mono, fontSize: 28, color: C.ink, background: C.sheet, border: `2px solid ${C.slate}`, padding: "12px 22px", borderRadius: 8 }}>
          every other amount: <b>Helvetica</b>
        </div>
        <div style={{ fontFamily: F.mono, fontSize: 28, color: "white", background: C.stamp, textAlign: "right", padding: "12px 22px", borderRadius: 8 }}>
          this total: <b>Times-Roman</b><br />₹45,500 still underneath
        </div>
      </div>

      <Captions lines={[
        { from: 0.4, to: 4.6, text: "A hospital bill. ₹45,500." },
        { from: 4.6, to: 7.6, text: "A white box over the real total, and a new number typed on top." },
        { from: 7.6, to: 11.6, text: "₹3,000 more. Would a reviewer catch it? Would an AI?" },
      ]} />
    </Scene>
  );
};
