import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export default function AppHeader() {
  const { email, signOut } = useAuth();
  return (
    <header className="app-header">
      <Link to="/" className="brand">
        <span className="brand-mark" aria-hidden="true" />
        ClaimLens
      </Link>
      <div className="app-header-user">
        <span className="mono">{email}</span>
        <button className="btn btn-quiet" onClick={() => void signOut()}>Sign out</button>
      </div>
    </header>
  );
}
