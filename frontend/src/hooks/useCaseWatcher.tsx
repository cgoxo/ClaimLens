import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { CaseSummary, Status } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { useToast } from "../components/Toast";
import { finishedText, notifyFinished } from "../lib/notify";

const RUNNING = new Set<Status>(["QUEUED", "READING", "CHECKING", "PROVING"]);
const FINAL = new Set<Status>(["READY", "FAILED"]);

interface Watcher {
  cases: CaseSummary[];
  /** a case was just uploaded: poll now, and notify when it finishes even if that happens before the next poll */
  track(id: string): void;
  refresh(): Promise<void>;
}

const WatcherContext = createContext<Watcher>({ cases: [], track: () => {}, refresh: async () => {} });

/** One app-wide poll of the case list while anything runs; notifies when a running case finishes. */
export function CaseWatcherProvider({ children, intervalMs = 5000 }: { children: ReactNode; intervalMs?: number }) {
  const { status, client } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const last = useRef(new Map<string, Status>()); // status seen on the previous poll
  const notified = useRef(new Set<string>());
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const signedIn = status === "signedIn";

  const refresh = useCallback(async () => {
    clearTimeout(timer.current);
    let list: CaseSummary[];
    try {
      list = await client.listCases();
    } catch {
      timer.current = setTimeout(() => void refresh(), intervalMs); // network blip: try again later
      return;
    }
    for (const c of list) {
      const before = last.current.get(c.id);
      if (before && RUNNING.has(before) && FINAL.has(c.status) && !notified.current.has(c.id)) {
        notified.current.add(c.id);
        const open = () => {
          window.focus();
          navigate(`/cases/${c.id}`);
        };
        if (!notifyFinished(c, open)) toast(finishedText(c), open);
      }
      last.current.set(c.id, c.status);
    }
    setCases(list);
    if (list.some((c) => RUNNING.has(c.status))) timer.current = setTimeout(() => void refresh(), intervalMs);
  }, [client, intervalMs, navigate, toast]);

  const track = useCallback((id: string) => {
    if (!last.current.has(id) || FINAL.has(last.current.get(id)!)) last.current.set(id, "QUEUED");
    void refresh();
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
