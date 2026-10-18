import React from "react";
import { interpolate } from "remotion";
import { C, F } from "../theme";
import { cue } from "../cues";
import { Captions, Kicker, Paper, Scene, ease, prog, useT } from "../components/ui";

type Node = { x: number; y: number; w: number; h: number; title: string; sub: string; color: string; at: number };

// Each service lights up as the narration names it (see cues.ts); the numbers are fallbacks without a voiceover
const T = {
  auth: cue("cloud", "Firebase", 1.0),
  run: cue("cloud", "Cloud Run", 4.2),
  tasks: cue("cloud", "Cloud Tasks", 12.2),
  firestore: cue("cloud", "Firestore", 8.2),
  storage: cue("cloud", "Cloud Storage", 8.8),
  docai: cue("cloud", "Document AI", 17.2),
  gemini: cue("cloud", "Vertex", 17.8),
  ship: cue("cloud", "Every release", 22.0),
};

const N: Record<string, Node> = {
  auth: { x: 260, y: 190, w: 360, h: 112, title: "Firebase Authentication", sub: "Google sign-in, ID tokens", color: C.gYellow, at: T.auth },
  browser: { x: 260, y: 430, w: 360, h: 112, title: "Reviewer's browser", sub: "React + Vite + TypeScript", color: C.slate, at: Math.max(0.6, T.auth - 0.4) },
  run: { x: 740, y: 260, w: 440, h: 360, title: "Cloud Run · claimlens-api", sub: "asia-south1, Mumbai · scales to zero", color: C.gBlue, at: T.run },
  tasks: { x: 740, y: 690, w: 440, h: 112, title: "Cloud Tasks · claimlens-jobs", sub: "calls back · 3 attempts · runs once", color: C.gRed, at: T.tasks },
  storage: { x: 1310, y: 150, w: 420, h: 104, title: "Cloud Storage", sub: "uploaded files, page images", color: C.gGreen, at: T.storage },
  firestore: { x: 1310, y: 280, w: 420, h: 104, title: "Firestore", sub: "cases, findings, invoices, chats", color: C.gYellow, at: T.firestore },
  docai: { x: 1310, y: 410, w: 420, h: 104, title: "Document AI · OCR", sub: "scanned and photographed pages", color: C.gBlue, at: T.docai },
  gemini: { x: 1310, y: 540, w: 420, h: 120, title: "Vertex AI · Gemini 2.5 Flash", sub: "facts, policy rules, summary, chat agent", color: C.gBlue, at: T.gemini },
};

const center = (n: Node) => ({ x: n.x + n.w / 2, y: n.y + n.h / 2 });
const edgePoint = (a: Node, b: Node) => {
  // where the line from a's centre towards b's centre leaves a's box
  const ca = center(a), cb = center(b);
  const dx = cb.x - ca.x, dy = cb.y - ca.y;
  const sx = dx === 0 ? Infinity : (a.w / 2) / Math.abs(dx);
  const sy = dy === 0 ? Infinity : (a.h / 2) / Math.abs(dy);
  const s = Math.min(sx, sy);
  return { x: ca.x + dx * s, y: ca.y + dy * s };
};

const LINKS: [string, string, number][] = [
  ["browser", "auth", T.auth + 0.4], ["browser", "run", T.run + 0.6], ["run", "storage", T.storage + 0.4], ["run", "firestore", T.firestore + 0.4],
  ["run", "tasks", T.tasks + 0.4], ["run", "docai", T.docai + 0.4], ["run", "gemini", T.gemini + 0.4],
];

// packets: [from, to, start second, travel seconds]
const PACKETS: [string, string, number, number][] = [
  ["browser", "auth", T.auth + 0.8, 0.7], ["auth", "browser", T.auth + 1.6, 0.7], ["browser", "run", T.run + 1.1, 0.9],
  ["run", "firestore", T.firestore + 1.0, 0.7], ["run", "storage", T.storage + 1.0, 0.7],
  ["run", "tasks", T.tasks + 1.0, 0.8], ["tasks", "run", T.tasks + 2.4, 0.8],
  ["run", "docai", T.docai + 1.0, 0.7], ["run", "gemini", T.gemini + 1.0, 0.7], ["gemini", "run", T.gemini + 1.9, 0.7], ["run", "firestore", T.gemini + 2.7, 0.7],
];

const SHIP: [string, string][] = [
  ["GitHub Actions CI/CD", "tests → build → deploy → smoke check"],
  ["Workload Identity Federation", "keyless deploys, no stored keys"],
  ["Artifact Registry + Cloud Build", "one image: React + FastAPI"],
  ["Secret Manager", "Firebase key, never in git"],
  ["Cloud Logging", "JSON logs per case, no patient data"],
  ["Terraform", "every resource as code"],
];

const Box: React.FC<{ n: Node; children?: React.ReactNode }> = ({ n, children }) => {
  const { t } = useT();
  const p = prog(t, n.at, 0.5);
  const glow = Math.max(0, 1 - Math.abs(t - n.at - 0.6) / 0.9);
  return (
    <div style={{ position: "absolute", left: n.x, top: n.y, width: n.w, height: n.h, opacity: p, transform: `scale(${0.9 + 0.1 * p})`,
      background: C.sheet, border: `2px solid ${n.color}`, borderLeft: `10px solid ${n.color}`, borderRadius: 10, padding: "18px 22px",
      boxShadow: `0 14px 34px rgba(30,28,25,0.12), 0 0 ${40 * glow}px ${n.color}66` }}>
      <div style={{ fontFamily: F.body, fontWeight: 600, fontSize: 27, color: C.ink }}>{n.title}</div>
      <div style={{ fontFamily: F.body, fontSize: 20, color: C.inkSoft, marginTop: 6 }}>{n.sub}</div>
      {children}
    </div>
  );
};

export const Cloud: React.FC = () => {
  const { t } = useT();
  const retry = prog(t, T.tasks + 2.0, 0.4) * (1 - prog(t, T.docai - 0.4, 0.4));
  const ship = prog(t, T.ship - 0.2, 0.5);
  return (
    <Scene>
      <Paper />
      <Kicker color={C.gBlue}>Built on Google Cloud · Mumbai region</Kicker>

      {/* opening title, while the narration says where it runs; it hands over to the diagram */}
      {(() => {
        const o = Math.min(prog(t, 0.2, 0.5), 1 - prog(t, T.auth - 0.6, 0.4));
        if (o <= 0) return null;
        return (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            gap: 26, opacity: o, transform: `scale(${0.96 + 0.04 * prog(t, 0.2, 0.8)})` }}>
            <div style={{ display: "flex", gap: 16 }}>
              {[C.gBlue, C.gRed, C.gYellow, C.gGreen].map((c, i) => (
                <div key={c} style={{ width: 26, height: 26, borderRadius: 13, background: c, opacity: prog(t, 0.3 + i * 0.12, 0.3) }} />
              ))}
            </div>
            <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 120, color: C.ink, lineHeight: 1 }}>Google Cloud</div>
            <div style={{ fontFamily: F.mono, fontSize: 32, color: C.inkSoft, opacity: prog(t, 1.0, 0.5) }}>Mumbai region · asia-south1</div>
          </div>
        );
      })()}

      <svg style={{ position: "absolute", inset: 0 }} width={1920} height={1080}>
        {LINKS.map(([a, b, at]) => {
          const p = prog(t, at, 0.6);
          const s = edgePoint(N[a], N[b]), e = edgePoint(N[b], N[a]);
          return <line key={a + b} x1={s.x} y1={s.y} x2={s.x + (e.x - s.x) * p} y2={s.y + (e.y - s.y) * p} stroke="#b9b09e" strokeWidth={3} strokeDasharray="8 7" />;
        })}
        {PACKETS.map(([a, b, at, d], i) => {
          if (t < at || t > at + d) return null;
          const s = edgePoint(N[a], N[b]), e = edgePoint(N[b], N[a]);
          const p = ease((t - at) / d);
          return <circle key={i} cx={s.x + (e.x - s.x) * p} cy={s.y + (e.y - s.y) * p} r={11} fill={N[b].color} stroke="white" strokeWidth={3} />;
        })}
      </svg>

      {Object.entries(N).map(([k, n]) => (
        <Box key={k} n={n}>
          {k === "run" && (
            <div style={{ marginTop: 22, display: "grid", gap: 12 }}>
              {[["FastAPI API + the React app", T.run + 1.2], ["Analysis pipeline: read → check → prove → score", T.run + 1.8], ["Gemini chat agent with read-only tools", T.run + 2.4]].map(([s, at]) => (
                <div key={s as string} style={{ opacity: prog(t, at as number, 0.4), fontFamily: F.mono, fontSize: 19, color: C.ink, background: "#efe9dc",
                  padding: "10px 14px", borderRadius: 6 }}>{s}</div>
              ))}
            </div>
          )}
        </Box>
      ))}

      {/* retry badge on the queue */}
      <div style={{ position: "absolute", left: 1200, top: 714, opacity: retry, fontFamily: F.mono, fontSize: 22, color: C.gRed,
        background: "white", border: `2px solid ${C.gRed}`, padding: "8px 14px", borderRadius: 8 }}>
        instance died? retried · duplicate? skipped
      </div>

      <div style={{ position: "absolute", left: 110, right: 110, top: 838, opacity: ship, display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 14 }}>
        {SHIP.map(([a, b], i) => {
          const p = prog(t, T.ship + i * 0.25, 0.4);
          return (
            <div key={a} style={{ opacity: p, transform: `translateY(${(1 - p) * 20}px)`, background: C.ink, color: "#fbf8f1", borderRadius: 8, padding: "12px 14px" }}>
              <div style={{ fontFamily: F.body, fontWeight: 600, fontSize: 19 }}>{a}</div>
              <div style={{ fontFamily: F.body, fontSize: 15, opacity: 0.75, marginTop: 4 }}>{b}</div>
            </div>
          );
        })}
      </div>

      <Captions lines={[
        { from: 0.6, to: 4.1, text: "Reviewers sign in with Google through Firebase Authentication." },
        { from: 4.2, to: 8.1, text: "One Cloud Run service serves the app, the API, the pipeline and the agent." },
        { from: 8.2, to: 12.1, text: "Files go to Cloud Storage. Cases, findings and invoices go to Firestore." },
        { from: 12.2, to: 17.1, text: "Cloud Tasks runs each analysis: retried if it fails, never run twice." },
        { from: 17.2, to: 21.9, text: "Document AI reads scans and photos. Gemini 2.5 Flash on Vertex AI reads the meaning." },
        { from: 22.0, to: 27.8, text: "Shipped by CI on every push, with keyless deploys, all in Terraform." },
      ]} />
    </Scene>
  );
};
