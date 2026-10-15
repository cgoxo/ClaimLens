import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ApiError, type Client } from "../api/client";
import type { CaseSummary, Status } from "../api/types";
import { AuthContext } from "../auth/AuthProvider";
import { ToastProvider } from "../components/Toast";
import { notifyFinished } from "../lib/notify";
import { CaseWatcherProvider, useCaseWatcher } from "./useCaseWatcher";

vi.mock("../lib/notify", async (original) => ({
  ...(await original<typeof import("../lib/notify")>()),
  notifyFinished: vi.fn(() => true),
}));

const row = (id: string, status: Status, unseen = false): CaseSummary => ({
  id, status, risk: status === "READY" ? "high" : null, score: null, created_at: "2026-10-16T10:00:00Z",
  progress: null, findings_count: 3, unseen,
});

function Probe() {
  const { cases, track } = useCaseWatcher();
  return (
    <>
      <p>{cases.map((c) => `${c.id}:${c.status}`).join(",")}</p>
      <button onClick={() => track("new1")}>track</button>
    </>
  );
}

function setup(lists: CaseSummary[][], listCases = vi.fn()) {
  let call = 0;
  if (lists.length) listCases.mockImplementation(async () => lists[Math.min(call++, lists.length - 1)]);
  const tree = (status: "signedIn" | "signedOut") => (
    <AuthContext.Provider value={{
      status, email: "a@x.com", error: null, mode: "dev" as const,
      signInGoogle: vi.fn(), signInDev: vi.fn(), signOut: vi.fn(), client: { listCases } as unknown as Client,
    }}>
      <ToastProvider>
        <MemoryRouter>
          <CaseWatcherProvider><Probe /></CaseWatcherProvider>
        </MemoryRouter>
      </ToastProvider>
    </AuthContext.Provider>
  );
  const { rerender } = render(tree("signedIn"));
  setup.signOut = () => rerender(tree("signedOut"));
  return listCases;
}
setup.signOut = () => {};

const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(notifyFinished).mockClear().mockReturnValue(true);
});
afterEach(() => {
  vi.useRealTimers();
  document.title = "ClaimLens";
});

test("polls while a case runs and stops once none are running", async () => {
  const listCases = setup([[row("a", "CHECKING")], [row("a", "READY")]]);
  await tick(0);
  expect(listCases).toHaveBeenCalledTimes(1);
  await tick(5000);
  expect(listCases).toHaveBeenCalledTimes(2);
  await tick(15000);
  expect(listCases).toHaveBeenCalledTimes(2);
});

test("notifies once when a running case finishes", async () => {
  setup([[row("a", "CHECKING")], [row("a", "READY")], [row("a", "READY")]]);
  await tick(0);
  await tick(5000);
  expect(notifyFinished).toHaveBeenCalledTimes(1);
  expect(vi.mocked(notifyFinished).mock.calls[0][0].id).toBe("a");
});

test("falls back to a toast when no system notification was shown", async () => {
  vi.mocked(notifyFinished).mockReturnValue(false);
  setup([[row("a", "CHECKING")], [row("a", "READY")]]);
  await tick(0);
  await tick(5000);
  expect(screen.getByRole("button", { name: "Case a ready: HIGH risk, 3 findings" })).toBeInTheDocument();
});

test("cases already finished on first load notify nothing", async () => {
  setup([[row("a", "READY"), row("b", "FAILED")]]);
  await tick(0);
  expect(notifyFinished).not.toHaveBeenCalled();
});

test("two cases finishing in the same poll notify twice", async () => {
  setup([[row("a", "READING"), row("b", "CHECKING")], [row("a", "READY"), row("b", "READY")]]);
  await tick(0);
  await tick(5000);
  expect(notifyFinished).toHaveBeenCalledTimes(2);
});

test("track wakes polling and a tracked case that finishes fast still notifies", async () => {
  const listCases = setup([[row("a", "READY")], [row("a", "READY"), row("new1", "READY")]]);
  await tick(0);
  await tick(10000);
  expect(listCases).toHaveBeenCalledTimes(1);
  await act(async () => screen.getByText("track").click());
  await tick(0);
  expect(listCases).toHaveBeenCalledTimes(2);
  expect(notifyFinished).toHaveBeenCalledTimes(1);
});

test("tab title counts unseen finished cases", async () => {
  setup([[row("a", "READY", true), row("b", "FAILED", true), row("c", "READY")]]);
  await tick(0);
  expect(document.title).toBe("(2) ClaimLens");
});

test("signing out stops polling, even when two refreshes overlapped", async () => {
  const listCases = setup([[row("a", "CHECKING")]]);
  await tick(0);
  // slow responses, so the timer's refresh and track()'s refresh are in flight together (as on upload)
  listCases.mockImplementation(() => new Promise((done) => setTimeout(() => done([row("a", "CHECKING")]), 100)));
  await tick(5000);
  await act(async () => screen.getByText("track").click());
  await tick(200);
  setup.signOut();
  const calls = listCases.mock.calls.length;
  await tick(30000);
  expect(listCases.mock.calls.length).toBe(calls);
});

test("a 401 or 403 is not retried", async () => {
  const listCases = vi.fn(async () => { throw new ApiError(401, "Sign in required"); });
  setup([], listCases);
  await tick(0);
  expect(listCases).toHaveBeenCalledTimes(1);
  await tick(30000);
  expect(listCases).toHaveBeenCalledTimes(1);
});
