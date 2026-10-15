import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { ToastProvider } from "./components/Toast";
import { CaseWatcherProvider } from "./hooks/useCaseWatcher";
import CasePage from "./pages/CasePage";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <p className="loading">Opening the case file…</p>;
  if (status !== "signedIn") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
      <BrowserRouter>
        <CaseWatcherProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<RequireAuth><UploadPage /></RequireAuth>} />
          <Route path="/cases/:id" element={<RequireAuth><CasePage /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </CaseWatcherProvider>
      </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
