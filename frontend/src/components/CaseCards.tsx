import { useState, type DragEvent } from "react";
import type { CardRole } from "../api/types";
import { checkFile, type DraftCard } from "../lib/upload";

const TITLES: Record<CardRole, string> = { claim: "Claim", policy: "Policy" };
const HINTS: Record<CardRole, string> = {
  claim: "The claim form, supporting documents and the bill: every page or photo, in order",
  policy: "The policy wording",
};

export const startingCards = (): DraftCard[] => [
  { id: "claim", role: "claim", files: [] },
  { id: "policy", role: "policy", files: [] },
];

interface Props {
  cards: DraftCard[];
  onChange(cards: DraftCard[]): void;
  busy: boolean;
  /** upload errors from the server, per file */
  errors: Map<File, string>;
}

/** The two upload forms: the claim (claim form, supporting documents and its one bill) and the policy. */
export default function CaseCards({ cards, onChange, busy, errors }: Props) {
  const [refused, setRefused] = useState<Record<string, string>>({});
  const update = (id: string, files: File[]) => onChange(cards.map((c) => (c.id === id ? { ...c, files } : c)));

  function add(card: DraftCard, list: FileList | null) {
    const files = [...(list ?? [])];
    const bad = files.map((f) => [f, checkFile(f)] as const).filter(([, e]) => e);
    setRefused((r) => ({ ...r, [card.id]: bad.map(([f, e]) => `${f.name}: ${e}`).join(" · ") }));
    const ok = files.filter((f) => !checkFile(f));
    if (ok.length) update(card.id, [...card.files, ...ok]);
  }

  function move(card: DraftCard, i: number, by: number) {
    const files = [...card.files];
    [files[i], files[i + by]] = [files[i + by], files[i]];
    update(card.id, files);
  }

  return (
    <div className="case-cards">
      {cards.map((card) => (
        <Card key={card.id} card={card} busy={busy} refused={refused[card.id]} errors={errors}
          onAdd={(list) => add(card, list)} onMove={(i, by) => move(card, i, by)}
          onRemoveFile={(i) => update(card.id, card.files.filter((_, j) => j !== i))} />
      ))}
    </div>
  );
}

function Card({ card, busy, refused, errors, onAdd, onMove, onRemoveFile }: {
  card: DraftCard; busy: boolean; refused?: string; errors: Map<File, string>;
  onAdd(list: FileList | null): void; onMove(i: number, by: number): void; onRemoveFile(i: number): void;
}) {
  const [over, setOver] = useState(false);
  const title = TITLES[card.role];
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
      <h2 id={`${inputId}-title`} className="tray-title">{title}</h2>
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
