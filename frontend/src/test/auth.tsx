import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import type { Client } from "../api/client";
import { AuthContext } from "../auth/AuthProvider";

/** Render a page signed in as a@x.com with a fake client, at `path`, with a stub case route. */
export function renderPage(ui: ReactNode, client: Partial<Client>, path = "/", pattern = "/") {
  const value = {
    status: "signedIn" as const, email: "a@x.com", error: null, mode: "dev" as const,
    signInGoogle: vi.fn(), signInDev: vi.fn(), signOut: vi.fn(), client: client as Client,
  };
  function CaseStub() {
    return <p>case page {useParams().id}</p>;
  }
  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={ui} />
          {pattern !== "/cases/:id" && <Route path="/cases/:id" element={<CaseStub />} />}
          <Route path="/" element={<p>upload page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}
