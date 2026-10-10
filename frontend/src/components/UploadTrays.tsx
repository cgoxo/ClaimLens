import { useState, type DragEvent } from "react";
import { checkFile, type UploadKind } from "../lib/upload";

interface TrayProps {
  kind: UploadKind;
  title: string;
  hint: string;
  accept: string;
  file: File | null;
  error: string | null;
  onFile(file: File): void;
}

function Tray({ kind, title, hint, accept, file, error, onFile }: TrayProps) {
  const [over, setOver] = useState(false);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  const id = `tray-${kind}`;
  return (
    <div className={`tray${over ? " is-over" : ""}${file && !error ? " is-filled" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
      <div className="tray-tab mono">{kind === "claim" ? "Exhibit A" : "Exhibit B"}</div>
      <h2 className="tray-title">{title}</h2>
      <label htmlFor={id} className="tray-drop">
        {file ? <span className="tray-file mono">{file.name}</span> : <span>Drop a file here or <u>choose one</u></span>}
        <span className="tray-hint">{hint}</span>
      </label>
      <input id={id} className="visually-hidden" type="file" accept={accept} aria-label={`${title} file`}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

export default function UploadTrays({ busy, error, onSubmit }: {
  busy: boolean;
  error: string | null;
  onSubmit(claim: File, policy: File): void;
}) {
  const [claim, setClaim] = useState<File | null>(null);
  const [policy, setPolicy] = useState<File | null>(null);
  const claimError = claim && checkFile("claim", claim);
  const policyError = policy && checkFile("policy", policy);
  const ready = claim && policy && !claimError && !policyError;

  return (
    <form className="trays" onSubmit={(e) => { e.preventDefault(); if (ready) onSubmit(claim, policy); }}>
      <div className="trays-row">
        <Tray kind="claim" title="Claim" hint="Bills, discharge summary, claim form · PDF, JPG or PNG · up to 20 MB"
          accept=".pdf,.jpg,.jpeg,.png" file={claim} error={claimError} onFile={setClaim} />
        <Tray kind="policy" title="Policy" hint="The policy wording · PDF · up to 20 MB"
          accept=".pdf" file={policy} error={policyError} onFile={setPolicy} />
      </div>
      {error && <p className="form-error form-error-block" role="alert">{error}</p>}
      <button className="btn btn-primary btn-large" type="submit" disabled={!ready || busy}>
        {busy ? "Opening…" : "Open case"}
      </button>
    </form>
  );
}
