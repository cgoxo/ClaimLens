import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import type { CaseSummary } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import AppHeader from "../components/AppHeader";
import CaseTable from "../components/CaseTable";
import UploadTrays from "../components/UploadTrays";

async function sampleFile(name: string): Promise<File> {
  const res = await fetch(`/samples/${name}`);
  if (!res.ok) throw new Error(`Couldn't load the sample ${name}`);
  return new File([await res.blob()], name, { type: "application/pdf" });
}

export default function UploadPage() {
  const { client } = useAuth();
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client.listCases().then(setCases).catch(() => setCases([]));
  }, [client]);

  async function open(getFiles: () => Promise<[File, File]>) {
    setBusy(true);
    setError(null);
    try {
      const [claim, policy] = await getFiles();
      const { case_id } = await client.createCase(claim, policy);
      navigate(`/cases/${case_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader />
      <main className="page upload-page">
        <section className="intro">
          <h1>Open a case file</h1>
          <p className="lede">
            Add the claim documents and the policy they're claimed against. ClaimLens checks for edited files,
            stories that don't add up, reused invoices and uncovered items, and cites the page for each.
          </p>
        </section>

        <UploadTrays busy={busy} error={error} onSubmit={(c, p) => void open(async () => [c, p])} />

        <div className="sample-row">
          <button className="btn btn-quiet" disabled={busy}
            onClick={() => void open(async () => [await sampleFile("claim.pdf"), await sampleFile("policy.pdf")])}>
            Try the sample claim
          </button>
          <span className="muted">A fictional cataract claim with a forged bill total.</span>
        </div>

        <section className="cases" aria-labelledby="cases-title">
          <h2 id="cases-title">Your cases</h2>
          <CaseTable cases={cases} />
        </section>
      </main>
    </>
  );
}
