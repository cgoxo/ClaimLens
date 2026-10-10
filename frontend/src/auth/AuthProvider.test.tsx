import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "../pages/LoginPage";
import { AuthProvider, useAuth } from "./AuthProvider";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  localStorage.clear();
  fetchMock = vi.fn().mockImplementation(async () => json(200, { email: "a@x.com" }));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

let auth: ReturnType<typeof useAuth>;
function Probe() {
  auth = useAuth();
  return <span data-testid="status">{auth.status}:{auth.email ?? ""}</span>;
}
const renderAuth = () =>
  render(
    <AuthProvider mode="dev">
      <Probe />
    </AuthProvider>,
  );

test("dev sign-in sets signedIn and sends X-Dev-User", async () => {
  renderAuth();
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signedOut:"));
  await act(async () => auth.signInDev("a@x.com"));
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signedIn:a@x.com"));
  await act(async () => { await auth.client.listCases().catch(() => {}); });
  const headers = new Headers(fetchMock.mock.calls.at(-1)![1].headers);
  expect(headers.get("X-Dev-User")).toBe("a@x.com");
});

test("a stored dev user is restored", async () => {
  localStorage.setItem("claimlens.devUser", "a@x.com");
  renderAuth();
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signedIn:a@x.com"));
});

test("403 from /api/me means forbidden", async () => {
  fetchMock.mockImplementation(async () => json(403, { detail: "nope" }));
  localStorage.setItem("claimlens.devUser", "b@x.com");
  renderAuth();
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("forbidden:b@x.com"));
});

test("sign out clears storage", async () => {
  localStorage.setItem("claimlens.devUser", "a@x.com");
  renderAuth();
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signedIn"));
  await act(async () => auth.signOut());
  expect(screen.getByTestId("status")).toHaveTextContent("signedOut:");
  expect(localStorage.getItem("claimlens.devUser")).toBeNull();
});

test("a 401 mid-session signs the user out", async () => {
  localStorage.setItem("claimlens.devUser", "a@x.com");
  renderAuth();
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signedIn"));
  fetchMock.mockImplementation(async () => json(401, { detail: "expired" }));
  await act(async () => { await auth.client.listCases().catch(() => {}); });
  expect(screen.getByTestId("status")).toHaveTextContent("signedOut:");
});

const renderLogin = () =>
  render(
    <AuthProvider mode="dev">
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </AuthProvider>,
  );

test("login page in dev mode has an email field and Enter", async () => {
  renderLogin();
  const field = await screen.findByLabelText(/email/i);
  await userEvent.type(field, "a@x.com");
  await userEvent.click(screen.getByRole("button", { name: "Enter" }));
  await waitFor(() => expect(localStorage.getItem("claimlens.devUser")).toBe("a@x.com"));
});

test("login page explains a refused account", async () => {
  fetchMock.mockImplementation(async () => json(403, { detail: "nope" }));
  localStorage.setItem("claimlens.devUser", "b@x.com");
  renderLogin();
  expect(await screen.findByText(/its email isn't verified/)).toBeInTheDocument();
});
