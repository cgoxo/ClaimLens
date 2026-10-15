import { useState, type DragEvent } from "react";
import type { BillKind, CardRole } from "../api/types";
import { checkFile, type DraftCard } from "../lib/upload";

const MAX_BILLS = 10;
const KINDS: BillKind[] = ["hospital", "pharmacy", "lab", "other"];
const TITLES: Record<CardRole, string> = {
  claim_form: "Claim form", bill: "Bill", supporting: "Supporting documents", policy: "Policy",
};
const HINTS: Record<CardRole, string> = {
  claim_form: "The filled-in claim form",
  bill: "Every page or photo of this one bill, in order",
  supporting: "Discharge summary, prescriptions, reports",
  policy: "The policy wording",
};

export const startingCards = (): DraftCard[] => [
  { id: "claim-form", role: "claim_form", kind: null, files: [] },
  { id: "b1", role: "bill", kind: "hospital", files: [] },
  { id: "supporting", role: "supporting", kind: null, files: [] },
  { id: "policy", role: "policy", kind: null, files: [] },
];

interface Props {
  cards: DraftCard[];
  onChange(cards: DraftCard[]): void;
  busy: boolean;
  /** upload errors from the server, per file */
  errors: Map<File, string>;
}

/** One claim, grouped the way the documents belong together: each bill its own card. */
export default function CaseCards({ cards, onChange, busy, errors }: Props) {
  const [refused, setRefused] = useState<Record<string, string>>({});
  const bills = cards.filter((c) => c.role === "bill");
  const title = (card: DraftCard) => card.role === "bill" ? `Bill ${bills.indexOf(card) + 1}` : TITLES[card.role];
  const update = (id: string, change: Partial<DraftCard>) =>
    onChange(cards.map((c) => (c.id === id ? { ...c, ...change } : c)));

  function add(card: DraftCard, list: FileList | null) {
    const files = [...(list ?? [])];
    const bad = files.map((f) => [f, checkFile(f)] as const).filter(([, e]) => e);
    setRefused((r) => ({ ...r, [card.id]: bad.map(([f, e]) => `${f.name}: ${e}`).join(" · ") }));
    const ok = files.filter((f) => !checkFile(f));
    if (ok.length) update(card.id, { files: [...card.files, ...ok] });
  }

  function move(card: DraftCard, i: number, by: number) {
    const files = [...card.files];
    [files[i], files[i + by]] = [files[i + by], files[i]];
    update(card.id, { files });
  }

  function addBill() {
    const n = Math.max(0, ...bills.map((b) => Number(b.id.slice(1)) || 0)) + 1;
    const at = cards.findIndex((c) => c.role === "supporting");
    const next = [...cards];
    next.splice(at < 0 ? cards.length : at, 0, { id: `b${n}`, role: "bill", kind: "hospital", files: [] });
    onChange(next);
  }

  return (
    <div className="case-cards">
      {cards.map((card) => (
        <Card key={card.id} card={card} title={title(card)} busy={busy} refused={refused[card.id]} errors={errors}
          onAdd={(list) => add(card, list)} onMove={(i, by) => move(card, i, by)}
          onRemoveFile={(i) => update(card.id, { files: card.files.filter((_, j) => j !== i) })}
          onKind={(kind) => update(card.id, { kind })}
          onRemove={card.role === "bill" && bills.length > 1 ? () => onChange(cards.filter((c) => c.id !== card.id)) : undefined} />
      ))}
      <button type="button" className="btn btn-quiet add-bill" disabled={busy || bills.length >= MAX_BILLS}
        onClick={addBill}>+ Add bill</button>
    </div>
  );
}

function Card({ card, title, busy, refused, errors, onAdd, onMove, onRemoveFile, onKind, onRemove }: {
  card: DraftCard; title: string; busy: boolean; refused?: string; errors: Map<File, string>;
  onAdd(list: FileList | null): void; onMove(i: number, by: number): void; onRemoveFile(i: number): void;
  onKind(kind: BillKind): void; onRemove?: () => void;
}) {
  const [over, setOver] = useState(false);
  const inputId = `card-${card.id}`;
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    onAdd(e.dataTransfer.files);
  };
  return (
    <section className={`tray case-card${over ? " is-over" : ""}${card.files.length ? " is-filled" : ""}`}
      aria-labelledby={`${inputId}-title`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
      <div className="case-card-head">
        <h2 id={`${inputId}-title`} className="tray-title">{title}</h2>
        {card.role === "bill" && (
          <select aria-label={`Kind of ${title}`} value={card.kind ?? "hospital"} disabled={busy}
            onChange={(e) => onKind(e.target.value as BillKind)}>
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        )}
        {onRemove && <button type="button" className="btn-icon" aria-label={`Remove ${title}`} disabled={busy}
          onClick={onRemove}>✕</button>}
      </div>
      {card.files.length > 0 && (
        <ol className="card-files">
          {card.files.map((file, i) => (
            <li key={`${file.name}-${i}`}>
              <span className="mono card-file-name">{file.name}</span>
              <span className="card-file-actions">
                <button type="button" className="btn-icon" aria-label={`Move ${file.name} up`} disabled={busy || i === 0}
                  onClick={() => onMove(i, -1)}>▲</button>
                <button type="button" className="btn-icon" aria-label={`Move ${file.name} down`}
                  disabled={busy || i === card.files.length - 1} onClick={() => onMove(i, 1)}>▼</button>
                <button type="button" className="btn-icon" aria-label={`Remove ${file.name}`} disabled={busy}
                  onClick={() => onRemoveFile(i)}>✕</button>
              </span>
              {errors.get(file) && <p className="form-error card-file-error">{errors.get(file)}</p>}
            </li>
          ))}
        </ol>
      )}
      <label htmlFor={inputId} className="tray-drop">
        <span>Drop files here or <u>choose</u></span>
        <span className="tray-hint">{HINTS[card.role]} · PDF, JPG or PNG · up to 20 MB each</span>
      </label>
      <input id={inputId} className="visually-hidden" type="file" multiple accept=".pdf,.jpg,.jpeg,.png"
        aria-label={`Add files to ${title}`} disabled={busy}
        onChange={(e) => { onAdd(e.target.files); e.target.value = ""; }} />
      {refused && <p className="form-error" role="alert">{refused}</p>}
    </section>
  );
}
