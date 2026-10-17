import React from "react";
import { interpolate } from "remotion";
import { C, F } from "../theme";
import { Captions, Kicker, Paper, Scene, ease, prog, useT } from "../components/ui";

type Node = { x: number; y: number; w: number; h: number; title: string; sub: string; color: string; at: number };

const N: Record<string, Node> = {
  auth: { x: 260, y: 190, w: 360, h: 112, title: "Firebase Authentication", sub: "Google sign-in, ID tokens", color: C.gYellow, at: 1.0 },
  browser: { x: 260, y: 430, w: 360, h: 112, title: "Reviewer's browser", sub: "React + Vite + TypeScript", color: C.slate, at: 0.8 },
  run: { x: 740, y: 260, w: 440, h: 360, title: "Cloud Run · claimlens-api", sub: "asia-south1 · one container", color: C.gBlue, at: 4.2 },
  tasks: { x: 740, y: 690, w: 440, h: 112, title: "Cloud Tasks · claimlens-jobs", sub: "calls back · 3 attempts · runs once", color: C.gRed, at: 12.2 },
  storage: { x: 1310, y: 150, w: 420, h: 104, title: "Cloud Storage", sub: "uploaded files, page images", color: C.gGreen, at: 8.2 },
  firestore: { x: 1310, y: 280, w: 420, h: 104, title: "Firestore", sub: "cases, findings, invoices, chats", color: C.gYellow, at: 8.8 },
  docai: { x: 1310, y: 410, w: 420, h: 104, title: "Document AI · OCR", sub: "scanned and photographed pages", color: C.gBlue, at: 17.2 },
  gemini: { x: 1310, y: 540, w: 420, h: 120, title: "Vertex AI · Gemini 2.5 Flash", sub: "facts, policy rules, summary, chat agent", color: C.gBlue, at: 17.8 },
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
  ["browser", "auth", 1.4], ["browser", "run", 4.8], ["run", "storage", 8.6], ["run", "firestore", 9.2],
  ["run", "tasks", 12.6], ["run", "docai", 17.6], ["run", "gemini", 18.2],
];

// packets: [from, to, start second, travel seconds]
const PACKETS: [string, string, number, number][] = [
  ["browser", "auth", 1.8, 0.7], ["auth", "browser", 2.6, 0.7], ["browser", "run", 5.3, 0.9],
  ["run", "storage", 9.4, 0.7], ["run", "firestore", 10.2, 0.7],
  ["run", "tasks", 13.2, 0.8], ["tasks", "run", 14.8, 0.8],
  ["run", "docai", 18.6, 0.7], ["run", "gemini", 19.5, 0.7], ["gemini", "run", 20.4, 0.7], ["run", "firestore", 21.2, 0.7],
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
  const retry = prog(t, 14.2, 0.4) * (1 - prog(t, 16.6, 0.4));
  const ship = prog(t, 22.0, 0.5);
  return (
    <Scene>
      <Paper />
      <Kicker color={C.gBlue}>Built on Google Cloud</Kicker>

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
              {[["FastAPI API + the React app", 5.6], ["Analysis pipeline: read → check → prove → score", 6.2], ["Gemini chat agent with read-only tools", 6.8]].map(([s, at]) => (
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
          const p = prog(t, 22.2 + i * 0.25, 0.4);
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
