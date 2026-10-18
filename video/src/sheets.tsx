import React from "react";
import { AbsoluteFill, Composition, Img, registerRoot, staticFile } from "remotion";

type Item = { n: number; scene: string; file: string; text: string };
const Sheet: React.FC<{ items: Item[] }> = ({ items }) => (
  <AbsoluteFill style={{ background: "#222", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, padding: 10 }}>
    {items.map((it) => (
      <div key={it.n} style={{ position: "relative" }}>
        <Img src={staticFile(it.file)} style={{ width: "100%", display: "block" }} />
        <div style={{ background: "#ffd400", color: "#000", font: "600 22px sans-serif", padding: "6px 10px" }}>
          {it.n}. [{it.scene}] {it.text}
        </div>
      </div>
    ))}
  </AbsoluteFill>
);
registerRoot(() => <Composition id="Sheet" component={Sheet as React.FC<any>} width={1920} height={1740} fps={30} durationInFrames={1} defaultProps={{ items: [] }} />);
