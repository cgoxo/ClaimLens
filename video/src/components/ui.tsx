import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, F } from "../theme";
import { VOICE } from "../timeline";

export const ease = Easing.bezier(0.65, 0, 0.35, 1);
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

export function useT() {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  return { t: frame / fps, frame, fps, end: durationInFrames / fps };
}

/** 0 -> 1 between `from` and `from + dur` seconds */
export function prog(t: number, from: number, dur = 0.5, easing = easeOut) {
  return interpolate(t, [from, from + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing });
}

/** Fades a scene in and out at its edges */
export const Scene: React.FC<{ children: React.ReactNode; bg?: string }> = ({ children, bg = C.paper }) => {
  const { t, end } = useT();
  const o = Math.min(prog(t, 0, 0.35), 1 - prog(t, end - 0.35, 0.35));
  return <AbsoluteFill style={{ background: bg, opacity: o }}>{children}</AbsoluteFill>;
};

/** Paper grain + soft vignette, under everything */
export const Paper: React.FC<{ dark?: boolean }> = ({ dark }) => (
  <AbsoluteFill style={{
    background: dark
      ? `radial-gradient(ellipse at 50% 40%, #24221c 0%, ${C.night} 70%)`
      : `radial-gradient(ellipse at 50% 35%, #fbf8f1 0%, ${C.paper} 60%, #e9e2d2 100%)`,
  }} />
);

export type Line = { from: number; to: number; text: React.ReactNode };

/** Bottom captions: one line at a time, readable with the sound off */
export const Captions: React.FC<{ lines: Line[]; dark?: boolean | ((t: number) => boolean); narrated?: boolean }> = ({ lines, dark: darkAt, narrated }) => {
  const { t } = useT();
  const dark = typeof darkAt === "function" ? darkAt(t) : darkAt;
  // with the voiceover on, the narration's own captions replace each scene's written ones
  if (VOICE && !narrated) return null;
  const line = lines.find((l) => t >= l.from && t < l.to);
  if (!line) return null;
  const o = Math.min(prog(t, line.from, 0.3), 1 - prog(t, line.to - 0.25, 0.25));
  const y = (1 - prog(t, line.from, 0.4)) * 16;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 44, pointerEvents: "none" }}>
      <div style={{
        opacity: o, transform: `translateY(${y}px)`, maxWidth: 1500, textAlign: "center",
        background: dark ? "rgba(251,248,241,0.95)" : "rgba(20,19,15,0.9)", color: dark ? C.ink : "#fbf8f1",
        fontFamily: F.body, fontWeight: 500, fontSize: 38, lineHeight: 1.3, padding: "16px 30px", borderRadius: 10,
        boxShadow: "0 12px 30px rgba(0,0,0,0.22)",
      }}>{line.text}</div>
    </AbsoluteFill>
  );
};

/** Small uppercase label that names the chapter */
export const Kicker: React.FC<{ children: React.ReactNode; at?: number; color?: string; top?: number }> = ({ children, at = 0.2, color = C.stamp, top = 54 }) => {
  const { t } = useT();
  const p = prog(t, at, 0.5);
  return (
    <div style={{ position: "absolute", top, left: 0, right: 0, textAlign: "center", opacity: p, transform: `translateY(${(1 - p) * -12}px)` }}>
      <span style={{ fontFamily: F.mono, fontWeight: 500, fontSize: 22, letterSpacing: "0.18em", textTransform: "uppercase", color }}>{children}</span>
    </div>
  );
};

/** The ClaimLens mark: the app's red lens plus its serif wordmark */
export const Logo: React.FC<{ size?: number; color?: string }> = ({ size = 120, color = C.ink }) => (
  <div style={{ display: "flex", alignItems: "center", gap: size * 0.22 }}>
    <svg width={size * 0.78} height={size * 0.78} viewBox="0 0 24 24" fill="none">
      <circle cx="10" cy="10" r="6.6" stroke={C.stamp} strokeWidth="2.4" />
      <path d="M15 15 L21 21" stroke={C.stamp} strokeWidth="2.8" strokeLinecap="round" />
    </svg>
    <span style={{ fontFamily: F.display, fontWeight: 600, fontSize: size, color, letterSpacing: "-0.01em", lineHeight: 1 }}>ClaimLens</span>
  </div>
);

/** A rubber stamp, as on the case page */
export const Stamp: React.FC<{ text: string; sub?: string; color?: string; size?: number; rotate?: number; at: number }> = ({ text, sub, color = C.stamp, size = 56, rotate = -6, at }) => {
  const { t } = useT();
  const p = prog(t, at, 0.35, Easing.bezier(0.2, 1.6, 0.4, 1));
  if (t < at) return null;
  return (
    <div style={{
      display: "inline-flex", flexDirection: "column", alignItems: "center", padding: `${size * 0.18}px ${size * 0.4}px`,
      border: `${Math.max(3, size / 14)}px solid ${color}`, color, borderRadius: 6, transform: `rotate(${rotate}deg) scale(${2 - p})`,
      opacity: Math.min(1, p * 1.4), fontFamily: F.display, fontWeight: 600, fontSize: size, letterSpacing: "0.04em", lineHeight: 1,
      background: "rgba(251,248,241,0.85)",
    }}>
      {text}
      {sub && <span style={{ fontFamily: F.mono, fontSize: size * 0.36, marginTop: size * 0.12, letterSpacing: "0.08em" }}>{sub}</span>}
    </div>
  );
};
