import React from "react";
import { C } from "../theme";
import { Captions, Paper, Scene } from "../components/ui";
import { Shots } from "../components/Shots";

const CENTER = { x: 735, y: 372, zoom: 1 };
const CARD = { x: 735, y: 263, zoom: 1.6 };   // progress card, centred until the viewer appears
const SPLIT = { x: 560, y: 300, zoom: 1.25 };  // then the card sits left of the document viewer

export const Upload: React.FC = () => (
  <Scene>
    <Paper />
    <Shots shots={[
      { src: "01-login.png", from: 0, to: 3.4, cropTop: 312,
        keys: [{ at: 0, ...CENTER }, { at: 2.6, x: 735, y: 400, zoom: 1.3 }],
        cursor: [{ at: 0.4, x: 1000, y: 650 }, { at: 2.2, x: 566, y: 512 }, { at: 2.6, x: 566, y: 512, click: true }] },
      { src: "02-upload-empty.png", from: 3.4, to: 9.0,
        keys: [{ at: 0, ...CENTER }, { at: 1.2, x: 735, y: 400, zoom: 1.12 }, { at: 3.6, x: 420, y: 560, zoom: 1.45 }],
        boxes: [{ from: 1.0, to: 3.2, x: 40, y: 292, w: 1390, h: 240, label: "Claim and policy: PDFs, scans or phone photos", color: C.slate }],
        cursor: [{ at: 0.6, x: 900, y: 700 }, { at: 3.9, x: 122, y: 656 }, { at: 4.4, x: 122, y: 656, click: true }] },
      { src: "03-progress-a.png", from: 9.0, to: 11.0, keys: [{ at: 0, x: 735, y: 420, zoom: 1.05 }] },
      { src: "03-progress-b.png", from: 11.0, to: 13.0, keys: [{ at: 0, ...CARD }] },
      { src: "03-progress-c.png", from: 13.0, to: 15.0, keys: [{ at: 0, ...SPLIT }] },
      { src: "03-progress-d.png", from: 15.0, to: 17.0, keys: [{ at: 0, ...SPLIT }] },
      { src: "03-progress-e.png", from: 17.0, to: 18.8, keys: [{ at: 0, ...SPLIT }] },
      { src: "04-ready-toast.png", from: 18.8, to: 24,
        keys: [{ at: 0, ...CENTER }, { at: 2.4, x: 1180, y: 600, zoom: 1.5 }],
        boxes: [{ from: 2.3, to: 5.2, x: 1110, y: 692, w: 330, h: 40, label: "Notified when it's ready", labelRight: true }] },
    ]} />
    <Captions lines={[
      { from: 0.3, to: 3.4, text: "Reviewers sign in with Google, through Firebase Authentication." },
      { from: 3.6, to: 8.9, text: "Upload the claim and its policy. We'll use the sample claim." },
      { from: 9.1, to: 11.0, text: "Files upload one by one, then the case is queued." },
      { from: 11.1, to: 14.9, text: "Cloud Tasks runs the analysis in the background, so it survives restarts." },
      { from: 15.0, to: 18.7, text: "Every page is read. Photos go through Document AI OCR. Gemini extracts the facts." },
      { from: 18.9, to: 23.8, text: "Under a minute later, the case is ready." },
    ]} />
  </Scene>
);
