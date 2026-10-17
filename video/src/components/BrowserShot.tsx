import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, F } from "../theme";
import { LIVE_URL } from "../timeline";

// Screenshots are full-screen Retina captures (2940 px wide). The page itself starts below Chrome's own bars,
// at `cropTop` image pixels; everything else here is in the page's CSS pixels (1470 x 745 viewport).
const PAGE_W = 1470;
const PAGE_H = 745;

export type Key = { at: number; x: number; y: number; zoom: number };
export type Box = { from: number; to: number; x: number; y: number; w: number; h: number; label?: string; color?: string; labelRight?: boolean };
export type Point = { at: number; x: number; y: number; click?: boolean };

type Props = {
  src: string;
  keys?: Key[];
  boxes?: Box[];
  cursor?: Point[];
  cropTop?: number;
  frameW?: number;
  enterAt?: number;
};

const ease = Easing.bezier(0.65, 0, 0.35, 1);

function camera(keys: Key[], t: number) {
  if (keys.length === 0) return { x: PAGE_W / 2, y: PAGE_H / 2, zoom: 1 };
  if (t <= keys[0].at) return keys[0];
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1], b = keys[i];
    if (t <= b.at) {
      const p = ease((t - a.at) / (b.at - a.at));
      return { x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p, zoom: a.zoom + (b.zoom - a.zoom) * p };
    }
  }
  return keys[keys.length - 1];
}

function cursorAt(points: Point[], t: number) {
  if (t <= points[0].at) return points[0];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    if (t <= b.at) {
      const p = ease((t - a.at) / (b.at - a.at));
      return { x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p };
    }
  }
  return points[points.length - 1];
}

export const BrowserShot: React.FC<Props> = ({ src, keys = [], boxes = [], cursor, cropTop = 422, frameW = 1640, enterAt = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const vw = frameW;
  const vh = (frameW / PAGE_W) * PAGE_H;
  const k = vw / PAGE_W;
  const cam = camera(keys, t);
  const s = k * cam.zoom;
  const left = Math.min(0, Math.max(vw - PAGE_W * s, vw / 2 - cam.x * s));
  const top = Math.min(0, Math.max(vh - PAGE_H * s, vh / 2 - cam.y * s));
  const toScreen = (x: number, y: number) => ({ x: left + x * s, y: top + y * s });

  const rise = interpolate(t - enterAt, [0, 0.6], [40, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const fade = interpolate(t - enterAt, [0, 0.4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{
        width: vw, borderRadius: 14, overflow: "hidden", background: C.sheet, transform: `translateY(${rise - 30}px)`, opacity: fade,
        boxShadow: "0 40px 80px rgba(30,28,25,0.25), 0 8px 20px rgba(30,28,25,0.12)", border: `1px solid ${C.rule}`,
      }}>
        <div style={{ height: 46, display: "flex", alignItems: "center", gap: 10, padding: "0 18px", background: "#ebe5d8", borderBottom: `1px solid ${C.rule}` }}>
          {["#ec6a5e", "#f4bf4f", "#61c554"].map((c) => <div key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />)}
          <div style={{ marginLeft: 24, flex: 1, height: 28, borderRadius: 14, background: C.sheet, display: "flex", alignItems: "center", padding: "0 14px", gap: 8, fontFamily: F.body, fontSize: 15, color: C.inkSoft }}>
            <span style={{ fontSize: 13 }}>🔒</span>{LIVE_URL}
          </div>
        </div>
        <div style={{ position: "relative", width: vw, height: vh, overflow: "hidden" }}>
          <Img src={staticFile(`shots/${src}`)} style={{ position: "absolute", left, top: top - (cropTop / 2) * s, width: PAGE_W * s }} />
          {boxes.map((b, i) => {
            const on = interpolate(t, [b.from, b.from + 0.35, b.to - 0.25, b.to], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            if (on <= 0) return null;
            const p = toScreen(b.x, b.y);
            const color = b.color ?? C.stamp;
            const grow = interpolate(t, [b.from, b.from + 0.45], [1.25, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
            return (
              <div key={i} style={{ position: "absolute", left: p.x, top: p.y, width: b.w * s, height: b.h * s, opacity: on,
                transform: `scale(${grow})`, transformOrigin: "center" }}>
                <div style={{ position: "absolute", inset: -6, border: `4px solid ${color}`, borderRadius: 6, boxShadow: `0 0 0 9999px rgba(20,19,15,${0.28 * on})` }} />
                {b.label && (
                  <div style={{ position: "absolute", ...(b.labelRight ? { right: -6 } : { left: -6 }), top: -54, whiteSpace: "nowrap", background: color, color: "white",
                    fontFamily: F.body, fontWeight: 600, fontSize: 22, padding: "8px 14px", borderRadius: 6 }}>{b.label}</div>
                )}
              </div>
            );
          })}
          {cursor && (() => {
            const c = cursorAt(cursor, t);
            const p = toScreen(c.x, c.y);
            const click = cursor.find((q) => q.click && t >= q.at && t < q.at + 0.5);
            const r = click ? interpolate(t - click.at, [0, 0.5], [0, 46]) : 0;
            return (
              <>
                {click && <div style={{ position: "absolute", left: p.x - r, top: p.y - r, width: r * 2, height: r * 2, borderRadius: "50%",
                  border: `3px solid ${C.stamp}`, opacity: 1 - (t - click.at) / 0.5 }} />}
                <svg width="34" height="34" viewBox="0 0 24 24" style={{ position: "absolute", left: p.x - 4, top: p.y - 2, filter: "drop-shadow(0 2px 3px rgba(0,0,0,0.35))" }}>
                  <path d="M4 2 L4 20 L9 15 L12.5 22 L15.5 20.6 L12 13.8 L19 13.8 Z" fill="white" stroke={C.ink} strokeWidth="1.4" strokeLinejoin="round" />
                </svg>
              </>
            );
          })()}
        </div>
      </div>
    </AbsoluteFill>
  );
};
