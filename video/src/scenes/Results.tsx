import React from "react";
import { C } from "../theme";
import { cue } from "../cues";
import { Captions, Paper, Scene } from "../components/ui";
import { Shots } from "../components/Shots";

const FULL = { x: 735, y: 372, zoom: 1 };
const END = 33;

// Each shot starts as the narration reaches it (see cues.ts); the numbers are fallbacks without a voiceover
const T_FACTS = cue("results", "Every fact", 5.3) - 0.3;
const T_MARK = cue("results", "Every problem", 9.7) - 0.3;
const T_HIDDEN = cue("results", "the real total hidden", 12.5);
const T_INVOICE = cue("results", "an invoice already", 15.8) - 0.3;
const T_RULES = cue("results", "The policy becomes", 20.8) - 0.3;
const T_WAIT = cue("results", "A waiting period", 23.5);
const T_PAY = cue("results", "Payable", 27.4) - 0.6;

export const Results: React.FC = () => (
  <Scene>
    <Paper />
    <Shots shots={[
      { src: "05-case-top.png", from: 0, to: T_FACTS,
        keys: [{ at: 0, ...FULL }, { at: 1.1, x: 527, y: 150, zoom: 2.1 }],
        boxes: [{ from: 1.4, to: T_FACTS + 0.2, x: 438, y: 86, w: 180, h: 112, label: "Score 100/100 · investigate" }] },
      { src: "08-facts.png", from: T_FACTS, to: T_MARK,
        keys: [{ at: 0, x: 330, y: 190, zoom: 1.5 }],
        boxes: [
          { from: 0.3, to: T_MARK - T_FACTS + 0.2, x: 40, y: 62, w: 570, h: 282, label: "Every fact cites its page", color: C.slate },
          { from: 1.1, to: T_MARK - T_FACTS + 0.2, x: 292, y: 251, w: 46, h: 22, color: C.amber },
        ] },
      { src: "09-finding-font.png", from: T_MARK, to: T_INVOICE,
        keys: [{ at: 0, ...FULL }, { at: 0.8, x: 560, y: 260, zoom: 1.45 }],
        boxes: [
          { from: 0.8, to: T_HIDDEN - T_MARK, x: 40, y: 143, w: 570, h: 226 },
          { from: 1.2, to: T_INVOICE - T_MARK + 0.2, x: 956, y: 265, w: 46, h: 20, label: "Rs 48,500 · Times-Roman", labelRight: true },
          { from: T_HIDDEN - T_MARK, to: T_INVOICE - T_MARK + 0.2, x: 40, y: 381, w: 570, h: 158, label: "The real total, hidden under a white box" },
        ] },
      { src: "10-finding-reused-invoice.png", from: T_INVOICE, to: T_RULES,
        keys: [{ at: 0, x: 560, y: 300, zoom: 1.45 }],
        boxes: [
          { from: 0.4, to: T_RULES - T_INVOICE + 0.2, x: 40, y: 209, w: 570, h: 194 },
          { from: 1.2, to: T_RULES - T_INVOICE + 0.2, x: 888, y: 177, w: 42, h: 18, label: "on a phone photo", color: C.amber },
        ] },
      { src: "07-policy-rules.png", from: T_RULES, to: T_PAY,
        keys: [{ at: 0, x: 330, y: 250, zoom: 1.45 }],
        boxes: [
          { from: 0.3, to: T_WAIT - T_RULES, x: 40, y: 60, w: 570, h: 430, label: "The policy as a rulebook, every rule cited", color: C.olive },
          { from: T_WAIT - T_RULES, to: T_PAY - T_RULES + 0.2, x: 40, y: 230, w: 570, h: 24, label: "Cataract: 24-month waiting period", color: C.olive },
        ] },
      { src: "06-settlement.png", from: T_PAY, to: END,
        keys: [{ at: 0, x: 330, y: 240, zoom: 1.5 }],
        boxes: [
          { from: 0.3, to: 2.6, x: 40, y: 272, w: 570, h: 46, label: "Applied line by line, in code", color: C.olive },
          { from: 2.6, to: END - T_PAY, x: 40, y: 360, w: 570, h: 36, label: "Payable: ₹0" },
        ] },
    ]} />
    <Captions lines={[
      { from: 0.3, to: T_FACTS, text: "Risk 100 out of 100. Recommendation: investigate." },
      { from: T_FACTS, to: T_MARK, text: "Every fact links back to the page it came from." },
      { from: T_MARK, to: T_INVOICE, text: "A total in a different font, with the real total hidden underneath." },
      { from: T_INVOICE, to: T_RULES, text: "An invoice already used in another claim, even on a photo." },
      { from: T_RULES, to: T_PAY, text: "The policy becomes a rulebook: cataract is in its waiting period." },
      { from: T_PAY, to: END - 0.3, text: "Payable, worked out line by line in code: ₹0." },
    ]} />
  </Scene>
);
