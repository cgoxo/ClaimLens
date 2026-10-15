import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import AppHeader from "../components/AppHeader";
import CaseCards, { startingCards } from "../components/CaseCards";
import CaseTable from "../components/CaseTable";
import { useCaseWatcher } from "../hooks/useCaseWatcher";
import { askPermission } from "../lib/notify";
import { submitCase, UploadFailed, type SubmitState } from "../lib/submitCase";
import { checkCards, type DraftCard } from "../lib/upload";

const SAMPLE: [string, DraftCard["role"], DraftCard["kind"], string, string][] = [
  ["claim-form", "claim_form", null, "claim-form.pdf", "application/pdf"],
  ["b1", "bill", "hospital", "hospital-bill.pdf", "application/pdf"],
  ["b2", "bill", "pharmacy", "pharmacy-bill.jpg", "image/jpeg"],
  ["supporting", "supporting", null, "discharge-summary.pdf", "application/pdf"],
  ["policy", "policy", null, "policy.pdf", "application/pdf"],
];

async function sampleCards(): Promise<DraftCard[]> {
  return Promise.all(SAMPLE.map(async ([id, role, kind, name, type]) => {
    const res = await fetch(`/samples/${name}`);
    if (!res.ok) throw new Error(`Couldn't load the sample ${name}`);
    return { id, role, kind, files: [new File([await res.blob()], name, { type })] };
  }));
}

export default function UploadPage() {
  const { client } = useAuth();
  const navigate = useNavigate();
  const { cases, track, refresh } = useCaseWatcher();
  const [cards, setCards] = useState<DraftCard[]>(startingCards);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<[number, number] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileErrors, setFileErrors] = useState(new Map<File, string>());
  const state = useRef<SubmitState>({ uploaded: new Set() }); // a retry continues the same draft

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // changing the cards after a failed attempt starts a fresh draft
  const edit = (next: DraftCard[]) => {
    state.current = { uploaded: new Set() };
    setFileErrors(new Map());
    setCards(next);
  };

  async function open(getCards: () => Promise<DraftCard[]>, fresh = false) {
    askPermission(); // must run inside the click, before any await
    if (fresh) state.current = { uploaded: new Set() };
    setBusy(true);
    setError(null);
    setFileErrors(new Map());
    try {
      const chosen = await getCards();
      if (fresh) setCards(chosen);
      const id = await submitCase(client, chosen, state.current, (done, total) => setProgress([done, total]));
      track(id);
      navigate(`/cases/${id}`);
    } catch (e) {
      if (e instanceof UploadFailed) setFileErrors(new Map([[e.file, e.message]]));
      else setError(e instanceof ApiError ? e.detail : e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
      setProgress(null);
    }
  }

  const problem = checkCards(cards);
  return (
    <>
      <AppHeader />
      <main className="page upload-page">
        <section className="intro">
          <h1>Open a case file</h1>
          <p className="lede">
            Add the claim, one card per bill, and the policy it's claimed against. ClaimLens checks for edited
            files, stories that don't add up, reused invoices and uncovered items, and cites the page for each.
          </p>
        </section>

        <form onSubmit={(e) => { e.preventDefault(); void open(async () => cards); }}>
          <CaseCards cards={cards} onChange={edit} busy={busy} errors={fileErrors} />
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="open-row">
            <button className="btn btn-primary btn-large" type="submit" disabled={busy || problem !== null}>
              {progress && busy ? `Uploading ${progress[0]} of ${progress[1]}…` : busy ? "Opening…" : "Open case"}
            </button>
            {problem && !busy && <span className="muted">{problem}</span>}
          </div>
        </form>

        <div className="sample-row">
          <button className="btn btn-quiet" disabled={busy} onClick={() => void open(sampleCards, true)}>
            Try the sample claim
          </button>
          <span className="muted">A fictional cataract claim: a forged hospital bill and a photographed pharmacy bill.</span>
        </div>

        <section className="cases" aria-labelledby="cases-title">
          <h2 id="cases-title">Your cases</h2>
          <CaseTable cases={cases} />
        </section>
      </main>
    </>
  );
}
