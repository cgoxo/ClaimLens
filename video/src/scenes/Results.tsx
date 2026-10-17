import React from "react";
import { C } from "../theme";
import { Captions, Paper, Scene } from "../components/ui";
import { Shots } from "../components/Shots";

const FULL = { x: 735, y: 372, zoom: 1 };

export const Results: React.FC = () => (
  <Scene>
    <Paper />
    <Shots shots={[
      { src: "05-case-top.png", from: 0, to: 9,
        keys: [{ at: 0, ...FULL }, { at: 1.3, x: 527, y: 150, zoom: 2.1 }, { at: 4.4, x: 527, y: 150, zoom: 2.1 },
          { at: 5.4, x: 330, y: 420, zoom: 1.75 }],
        boxes: [
          { from: 1.7, to: 4.6, x: 438, y: 86, w: 180, h: 112, label: "Score 100/100 · investigate" },
          { from: 5.8, to: 9.2, x: 40, y: 375, w: 570, h: 108, label: "Summary by Gemini, from proved findings only", color: C.slate },
        ] },
      { src: "09-finding-font.png", from: 9, to: 15.5,
        keys: [{ at: 0, ...FULL }, { at: 1.0, x: 560, y: 250, zoom: 1.45 }],
        boxes: [
          { from: 1.2, to: 6.2, x: 40, y: 143, w: 570, h: 226, color: C.stamp },
          { from: 2.0, to: 6.4, x: 956, y: 265, w: 46, h: 20, label: "Rs 48,500 · Times-Roman" },
        ] },
      { src: "10-finding-reused-invoice.png", from: 15.5, to: 21.5,
        keys: [{ at: 0, x: 560, y: 300, zoom: 1.45 }],
        boxes: [
          { from: 0.6, to: 5.8, x: 40, y: 209, w: 570, h: 194, color: C.stamp },
          { from: 1.4, to: 6.0, x: 888, y: 177, w: 42, h: 18, label: "on a phone photo", color: C.amber },
        ] },
      { src: "11-finding-waiting-period.png", from: 21.5, to: 27,
        keys: [{ at: 0, x: 600, y: 360, zoom: 1.45 }],
        boxes: [
          { from: 0.8, to: 5.4, x: 862, y: 225, w: 212, h: 24, label: "Clause 3.2, proved on policy p.2", color: C.olive, labelRight: true },
          { from: 1.8, to: 5.4, x: 204, y: 407, w: 162, h: 22, color: C.amber },
        ] },
      { src: "06-settlement.png", from: 27, to: 32,
        keys: [{ at: 0, x: 330, y: 240, zoom: 1.5 }],
        boxes: [
          { from: 0.6, to: 2.8, x: 40, y: 272, w: 570, h: 46, label: "Deducted in code, line by line", color: C.olive },
          { from: 2.8, to: 5.2, x: 40, y: 360, w: 570, h: 36, label: "Payable under the policy" },
        ] },
    ]} />
    <Captions lines={[
      { from: 0.3, to: 4.6, text: "Risk 100 out of 100. Recommendation: investigate." },
      { from: 4.7, to: 8.9, text: "Gemini writes the summary, but plain code sets the score." },
      { from: 9.1, to: 15.4, text: "Every finding is marked on its page. This total is in a different font from the rest." },
      { from: 15.6, to: 21.4, text: "This pharmacy invoice was already used in another claim, even on a photo." },
      { from: 21.6, to: 26.9, text: "The policy becomes a rulebook. Cataract is still in its 24-month waiting period." },
      { from: 27.1, to: 31.8, text: "So the settlement, worked out line by line in code, is ₹0." },
    ]} />
  </Scene>
);
