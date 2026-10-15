import { useEffect, useState } from "react";
import type { Client } from "../api/client";
import type { CaseCard, Citation, PageMeta } from "../api/types";
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
}

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

export default function PageViewer({ caseId, pages, cards = [], selected, selectedNumber, selectedDetail, selectionKey = 0, client }: Props) {
  const [doc, setDoc] = useState(selected?.doc ?? "claim");
  const [page, setPage] = useState(selected?.page ?? 1);
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

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
            {src ? <img src={src} alt={`${doc} page ${page}`} /> : <div className="sheet-loading" aria-hidden="true" />}
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
