import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import type { CaseSummary, Status } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { useToast } from "../components/Toast";
import { finishedText, notifyFinished } from "../lib/notify";

const RUNNING = new Set<Status>(["QUEUED", "READING", "CHECKING", "PROVING"]);
const FINAL = new Set<Status>(["READY", "FAILED", "REJECTED"]);

interface Watcher {
  cases: CaseSummary[];
  /** a case was just uploaded: poll now, and notify when it finishes even if that happens before the next poll */
  track(id: string): void;
  refresh(fresh?: boolean): Promise<void>;
}

const WatcherContext = createContext<Watcher>({ cases: [], track: () => {}, refresh: async () => {} });

/** One app-wide poll of the case list while anything runs; notifies when a running case finishes. */
export function CaseWatcherProvider({ children, intervalMs = 5000 }: { children: ReactNode; intervalMs?: number }) {
  const { status, client } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  // navigate changes on every route change; keep refresh stable so navigation doesn't start extra polls
  const go = useRef(navigate);
  go.current = navigate;
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const last = useRef(new Map<string, Status>()); // status seen on the previous poll
  const notified = useRef(new Set<string>());
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const signedIn = status === "signedIn";
  const active = useRef(signedIn);
  active.current = signedIn;

  // exactly one pending poll at a time, and none once signed out
  const schedule = (run: () => void) => {
    clearTimeout(timer.current);
    if (active.current) timer.current = setTimeout(run, intervalMs);
  };

  const inFlight = useRef<Promise<void> | null>(null);
  const again = useRef(false); // a fresh list was asked for while an older request was out

  const poll = useCallback(async () => {
    clearTimeout(timer.current);
    let list: CaseSummary[];
    try {
      list = await client.listCases();
    } catch (e) {
      // signed out or refused: stop; anything else (a network blip): try again later
      if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) schedule(() => void refresh());
      return;
    }
    if (!active.current) return;
    for (const c of list) {
      const before = last.current.get(c.id);
      if (before && RUNNING.has(before) && FINAL.has(c.status) && !notified.current.has(c.id)) {
        notified.current.add(c.id);
        const open = () => {
          window.focus();
          go.current(`/cases/${c.id}`);
        };
        if (!notifyFinished(c, open)) toast(finishedText(c), open);
      }
      last.current.set(c.id, c.status);
    }
    setCases(list);
    if (list.some((c) => RUNNING.has(c.status))) schedule(() => void refresh());
  }, [client, intervalMs, toast]);

  /** Fetch the list; a call while one is out shares it, and `fresh` asks for one more fetch after it. */
  const refresh = useCallback((fresh = false): Promise<void> => {
    if (inFlight.current) {
      if (fresh) again.current = true;
      return inFlight.current;
    }
    inFlight.current = poll().finally(() => {
      inFlight.current = null;
      if (again.current) {
        again.current = false;
        void refresh();
      }
    });
    return inFlight.current;
  }, [poll]);

  const track = useCallback((id: string) => {
    if (!last.current.has(id) || FINAL.has(last.current.get(id)!)) last.current.set(id, "QUEUED");
    void refresh(true);
  }, [refresh]);

  useEffect(() => {
    if (signedIn) void refresh();
    return () => clearTimeout(timer.current);
  }, [signedIn, refresh]);

  const unseen = cases.filter((c) => c.unseen).length;
  useEffect(() => {
    document.title = unseen > 0 ? `(${unseen}) ClaimLens` : "ClaimLens";
  }, [unseen]);

  const value = useMemo(() => ({ cases, track, refresh }), [cases, track, refresh]);
  return <WatcherContext.Provider value={value}>{children}</WatcherContext.Provider>;
}

export const useCaseWatcher = () => useContext(WatcherContext);
