import React from "react";
import { AbsoluteFill } from "remotion";
import { C, F } from "../theme";
import { Captions, Paper, Scene, prog, useT } from "../components/ui";
import { Shots } from "../components/Shots";

// The chat agent's tools (backend/claimlens/chat/tools.py): all read-only
const TOOLS = ["list_findings", "get_finding", "get_facts", "get_settlement", "search_text", "get_page", "view_region", "check_region"];

const ToolPanel: React.FC<{ from: number; to: number }> = ({ from, to }) => {
  const { t } = useT();
  const o = Math.min(prog(t, from, 0.4), 1 - prog(t, to - 0.3, 0.3));
  if (o <= 0) return null;
  return (
    <div style={{ position: "absolute", right: 200, top: 250, width: 640, opacity: o, transform: `translateX(${(1 - prog(t, from, 0.5)) * 40}px)`,
      background: C.night, color: "#fbf8f1", borderRadius: 12, padding: "26px 30px", boxShadow: "0 30px 60px rgba(0,0,0,0.35)" }}>
      <div style={{ fontFamily: F.mono, fontSize: 20, letterSpacing: "0.12em", textTransform: "uppercase", color: C.gYellow }}>Gemini function calling</div>
      <div style={{ fontFamily: F.display, fontSize: 40, fontWeight: 600, marginTop: 8 }}>Read-only tools over the case</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 22 }}>
        {TOOLS.map((name, i) => {
          const p = prog(t, from + 0.3 + i * 0.18, 0.3);
          return (
            <span key={name} style={{ opacity: p, transform: `scale(${0.8 + 0.2 * p})`, fontFamily: F.mono, fontSize: 24, padding: "8px 14px",
              borderRadius: 6, background: "#2b2924", border: `1px solid #45413a` }}>{name}()</span>
          );
        })}
      </div>
      <div style={{ fontFamily: F.body, fontSize: 22, color: "#cfc8ba", marginTop: 20 }}>It can look. It can't change anything.</div>
    </div>
  );
};

const Motto: React.FC<{ from: number }> = ({ from }) => {
  const { t } = useT();
  const o = prog(t, from, 0.5);
  if (o <= 0) return null;
  const words: [string, string][] = [["The agent investigates.", C.gBlue], ["Code verifies.", C.olive], ["A human decides.", C.stamp]];
  return (
    <AbsoluteFill style={{ background: `rgba(20,19,15,${0.82 * o})`, alignItems: "center", justifyContent: "center", gap: 18 }}>
      {words.map(([w, col], i) => {
        const p = prog(t, from + 0.2 + i * 0.45, 0.45);
        return <div key={w} style={{ opacity: p, transform: `translateY(${(1 - p) * 24}px)`, fontFamily: F.display, fontWeight: 600, fontSize: 92,
          color: "#fbf8f1", borderBottom: `6px solid ${col}`, lineHeight: 1.15 }}>{w}</div>;
      })}
    </AbsoluteFill>
  );
};

export const Agent: React.FC = () => (
  <Scene>
    <Paper />
    <Shots shots={[
      { src: "12-chat-typed.png", from: 0, to: 5,
        keys: [{ at: 0, x: 735, y: 400, zoom: 1 }, { at: 1.0, x: 340, y: 560, zoom: 1.55 }],
        boxes: [{ from: 1.2, to: 5.2, x: 40, y: 636, w: 496, h: 66, label: "Ask in plain English", color: C.slate }] },
      { src: "13-chat-thinking.png", from: 5, to: 8.4, keys: [{ at: 0, x: 340, y: 560, zoom: 1.55 }] },
      { src: "14-chat-answer.png", from: 8.4, to: 14,
        keys: [{ at: 0, x: 340, y: 540, zoom: 1.7 }],
        boxes: [
          { from: 0.5, to: 5.6, x: 40, y: 517, w: 570, h: 94, label: "Verified: every quote found on its page", color: C.olive },
        ] },
      { src: "15-area-typed.png", from: 14, to: 18,
        keys: [{ at: 0, x: 700, y: 420, zoom: 1.2 }],
        boxes: [
          { from: 0.4, to: 4.2, x: 860, y: 196, w: 180, h: 64, label: "Area drawn on the bill", color: C.amber },
          { from: 1.4, to: 4.2, x: 40, y: 669, w: 496, h: 60, color: C.slate },
        ] },
      { src: "16-area-answer.png", from: 18, to: 24,
        keys: [{ at: 0, x: 340, y: 450, zoom: 1.6 }],
        boxes: [{ from: 0.6, to: 6.0, x: 40, y: 343, w: 570, h: 206, label: "13,500 + 22,000 + 8,000 + 2,000 = 45,500", color: C.olive }] },
      { src: "17-proposal.png", from: 24, to: 35,
        keys: [{ at: 0, x: 340, y: 480, zoom: 1.65 }],
        boxes: [
          { from: 0.6, to: 4.8, x: 54, y: 471, w: 542, h: 122, label: "A proposal, not an action", color: C.slate },
          { from: 2.4, to: 5.0, x: 66, y: 547, w: 70, h: 32, label: "Only a human clicks Apply" },
        ] },
    ]} />
    <ToolPanel from={5.2} to={8.4} />
    <Motto from={29.2} />
    <Captions lines={[
      { from: 0.2, to: 4.0, text: "On a finished case, the reviewer can question a Gemini agent." },
      { from: 4.1, to: 7.4, text: "It answers by calling read-only tools over the case." },
      { from: 7.5, to: 13.0, text: "Its answers pass the same proof gate: each quote must be on the cited page." },
      { from: 13.1, to: 17.0, text: "Draw a box on any page and ask about just that area." },
      { from: 17.1, to: 23.0, text: "It adds up the lines itself: ₹45,500. The ₹48,500 total doesn't fit." },
      { from: 23.1, to: 28.1, text: "It can suggest a change, like dismissing a typo, but only as a proposal." },
    ]} />
  </Scene>
);
