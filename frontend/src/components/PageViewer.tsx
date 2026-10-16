import { useEffect, useRef, useState } from "react";
import type { Client } from "../api/client";
import type { BBox, Box, CaseCard, Citation, PageMeta } from "../api/types";
import { toPercentBox } from "../lib/highlight";

interface Props {
  caseId: string;
  pages: PageMeta[];
  /** the case's cards, for grouping the page strip; empty for cases from before cards */
  cards?: CaseCard[];
  selected: Citation | null;
  selectedNumber: number | null;
  selectedDetail: string;
  /** bumps on every selection, so re-selecting the same finding still returns to its page */
  selectionKey?: number;
  client: Client;
  /** when given, the viewer offers "Ask about an area"; called with a box in page points */
  onSelectArea?(box: Box): void;
}

/** A drag shorter than this many screen pixels (either way) is a stray click, not a selection. */
const MIN_DRAG_PX = 8;
type Drag = { x0: number; y0: number; x1: number; y1: number };

const DOCS = [["claim", "Claim"], ["policy", "Policy"]] as const;

/** Consecutive pages of one uploaded file, labelled with its name; pages from before cards fall under the document. */
function groups(pages: PageMeta[], cards: CaseCard[], doc: string): [string, PageMeta[]][] {
  const out: [string, PageMeta[]][] = [];
  for (const p of pages) {
    const file = cards.find((c) => c.id === p.card_id)?.files[p.file_index];
    const label = file?.name ?? (doc === "claim" ? "Claim" : "Policy");
    const last = out[out.length - 1];
    if (last && last[0] === label) last[1].push(p);
    else out.push([label, [p]]);
  }
  return out;
}

export default function PageViewer({ caseId, pages, cards = [], selected, selectedNumber, selectedDetail, selectionKey = 0, client, onSelectArea }: Props) {
  const [doc, setDoc] = useState(selected?.doc ?? "claim");
  const [page, setPage] = useState(selected?.page ?? 1);
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [selecting, setSelecting] = useState(false);
  const [drag, setDrag] = useState<Drag | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!selecting) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setSelecting(false); setDrag(null); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selecting]);

  useEffect(() => {
    if (selected) {
      setDoc(selected.doc);
      setPage(selected.page);
    }
  }, [selected, selectionKey]);

  const meta = pages.find((p) => p.doc === doc && p.page === page);
  const docPages = pages.filter((p) => p.doc === doc);

  useEffect(() => {
    let alive = true;
    setSrc(null);
    setFailed(false);
    if (!meta || meta.kind === "unreadable") return;
    client.pageImageUrl(caseId, doc, page).then(
      (url) => alive && setSrc(url),
      () => alive && setFailed(true),
    );
    return () => { alive = false; };
  }, [caseId, doc, page, meta, client, attempt]);

  // changing page or document abandons a half-made selection
  useEffect(() => setDrag(null), [doc, page]);

  const clamp = (v: number, max: number) => Math.min(max, Math.max(0, v));
  const imageRect = (fallback: Element) => (imgRef.current ?? fallback).getBoundingClientRect();
  /** pointer position in pixels from the page image's corner, kept inside the image */
  function local(e: React.PointerEvent<HTMLDivElement>) {
    const r = imageRect(e.currentTarget);
    return { x: clamp(e.clientX - r.left, r.width), y: clamp(e.clientY - r.top, r.height) };
  }
  function dragStart(e: React.PointerEvent<HTMLDivElement>) {
    const { x, y } = local(e);
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setDrag({ x0: x, y0: y, x1: x, y1: y });
  }
  function dragMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag) return;
    const { x, y } = local(e);
    setDrag({ ...drag, x1: x, y1: y });
  }
  function dragEnd(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag || !meta) return;
    const { x, y } = local(e);
    const d = { ...drag, x1: x, y1: y };
    setDrag(null);
    const r = imageRect(e.currentTarget);
    if (Math.abs(d.x1 - d.x0) < MIN_DRAG_PX || Math.abs(d.y1 - d.y0) < MIN_DRAG_PX || !r.width || !r.height) return;
    // pixels on screen to points on the page
    const sx = meta.width / r.width;
    const sy = meta.height / r.height;
    const bbox: BBox = [Math.min(d.x0, d.x1) * sx, Math.min(d.y0, d.y1) * sy, Math.max(d.x0, d.x1) * sx, Math.max(d.y0, d.y1) * sy];
    setSelecting(false);
    onSelectArea?.({ doc, page, bbox });
  }

  const here = selected && selected.doc === doc && selected.page === page ? selected : null;
  const box = here && here.source !== "metadata" && here.bbox && meta ? toPercentBox(here.bbox, meta.width, meta.height) : null;

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <div role="tablist" aria-label="Document" className="tabs">
          {DOCS.map(([key, label]) => (
            <button key={key} role="tab" aria-selected={doc === key} className="tab"
              onClick={() => { setDoc(key); setPage(1); }}>{label}</button>
          ))}
        </div>
        <div className="thumbs" aria-label="Pages">
          {groups(docPages, cards, doc).map(([label, group]) => (
            <div key={label} role="group" aria-label={label} className="thumb-group">
              <span className="thumb-group-label">{label}</span>
              {group.map((p) => (
                <button key={p.page} className="thumb mono" aria-label={`${doc} page ${p.page}`}
                  aria-current={p.page === page ? "true" : undefined} onClick={() => setPage(p.page)}>
                  {p.page}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {here?.source === "metadata" && (
        <div className="viewer-banner" role="note">
          <strong>File properties.</strong> {selectedDetail}
        </div>
      )}
      {here && here.source !== "metadata" && !here.bbox && (
        <div className="viewer-banner viewer-banner-quote" role="note">
          Quoted text: <q>{here.quote}</q>
        </div>
      )}

      {onSelectArea && meta && meta.kind !== "unreadable" && (
        <div className="viewer-tools">
          <button type="button" className="btn btn-quiet" aria-pressed={selecting}
            onClick={() => { setSelecting((v) => !v); setDrag(null); }}>
            {selecting ? "Cancel" : "Ask about an area"}
          </button>
          {selecting && <span className="muted small">Drag a box on the page. Esc to cancel.</span>}
        </div>
      )}

      <div className="sheet-frame">
        {!meta ? (
          <p className="page-empty">No pages.</p>
        ) : meta.kind === "unreadable" ? (
          <p className="page-empty">Page {page} is unreadable (scanned, and OCR is off).</p>
        ) : failed ? (
          <div className="page-empty">
            <p>Couldn't load page {page}</p>
            <button className="btn btn-quiet" onClick={() => setAttempt((n) => n + 1)}>Retry</button>
          </div>
        ) : (
          <div className="sheet" style={{
            aspectRatio: `${meta.width} / ${meta.height}`,
            // fit the whole page in the window, so the marker is never scrolled out of view
            width: `min(100%, calc((100vh - 170px) * ${meta.width / meta.height}))`,
          }}>
            {src ? <img ref={imgRef} src={src} alt={`${doc} page ${page}`} /> : <div className="sheet-loading" aria-hidden="true" />}
            {selecting && (
              <div data-testid="select-layer" className="select-layer" onPointerDown={dragStart}
                onPointerMove={dragMove} onPointerUp={dragEnd} onPointerCancel={() => setDrag(null)}>
                {drag && (
                  <div data-testid="drag-box" className="marker marker-dashed" style={{
                    left: Math.min(drag.x0, drag.x1), top: Math.min(drag.y0, drag.y1),
                    width: Math.abs(drag.x1 - drag.x0), height: Math.abs(drag.y1 - drag.y0),
                  }} />
                )}
              </div>
            )}
            {box && (
              <div data-testid="marker" className={`marker${here?.source === "hidden_layer" ? " marker-dashed" : ""}`}
                style={{ left: `${box.left}%`, top: `${box.top}%`, width: `${box.width}%`, height: `${box.height}%` }}>
                {selectedNumber && <span className="marker-tag mono">{selectedNumber}</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
