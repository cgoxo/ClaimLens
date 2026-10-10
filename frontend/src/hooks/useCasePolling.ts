import { useEffect, useState } from "react";
import { ApiError, type Client } from "../api/client";
import type { Case } from "../api/types";

const FINAL = new Set(["READY", "FAILED"]);
const FATAL = new Set([401, 403, 404]);
const LOST_AFTER = 5;

/** Fetch a case every `intervalMs` until it is READY or FAILED. */
export function useCasePolling(id: string, client: Client, intervalMs = 2000) {
  const [data, setData] = useState<Case | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    setData(null);
    setError(null);

    const poll = async () => {
      try {
        const c = await client.getCase(id);
        if (!alive) return;
        failures = 0;
        setConnectionLost(false);
        setData(c);
        if (FINAL.has(c.status)) return;
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && FATAL.has(e.status)) {
          setError(e);
          return;
        }
        failures += 1;
        if (failures >= LOST_AFTER) setConnectionLost(true);
      }
      // chain timeouts so a slow request never overlaps the next one
      timer = setTimeout(poll, intervalMs);
    };
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [id, client, intervalMs]);

  return { data, error, connectionLost, setData };
}
