import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export default function LoginPage() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (auth.status === "signedIn") return <Navigate to="/" replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (email.includes("@")) auth.signInDev(email);
  };
  const google = async () => {
    setError(null);
    try {
      await auth.signInGoogle();
    } catch {
      setError("Google sign-in was closed or failed. Please try again.");
    }
  };

  return (
    <main className="cover">
      <section className="cover-sheet" aria-labelledby="cover-title">
        <h1 id="cover-title" className="cover-title">ClaimLens</h1>
        <p className="cover-pitch">
          Upload an insurance claim and its policy. ClaimLens finds edited documents, stories that don't add up,
          reused invoices and items the policy won't cover, and marks the page each one is on.
        </p>

        {auth.status === "forbidden" ? (
          <div className="cover-alert" role="alert">
            <p>
              <strong>{auth.email}</strong> can't be used here: its email isn't verified. Sign in with a Google
              account instead.
            </p>
            <button className="btn btn-quiet" onClick={() => void auth.signOut()}>Sign out</button>
          </div>
        ) : auth.mode === "dev" ? (
          <form className="cover-form" onSubmit={submit}>
            <label htmlFor="dev-email">Email (dev sign-in)</label>
            <div className="cover-row">
              <input id="dev-email" type="email" required value={email} placeholder="you@example.com"
                onChange={(e) => setEmail(e.target.value)} />
              <button className="btn btn-primary" type="submit">Enter</button>
            </div>
          </form>
        ) : (
          <div className="cover-form">
            <button className="btn btn-primary btn-google" onClick={() => void google()} disabled={auth.status === "loading"}>
              Sign in with Google
            </button>
            {(error ?? auth.error) && <p className="form-error" role="alert">{error ?? auth.error}</p>}
          </div>
        )}
      </section>
    </main>
  );
}
