// System notifications when a case finishes. Every call is safe where the API is missing or blocked.
import type { CaseSummary } from "../api/types";

const api = (): typeof Notification | undefined =>
  typeof Notification === "undefined" ? undefined : Notification;

/** Ask once, from a click (browsers ignore requests that don't follow a user gesture). */
export function askPermission(): void {
  try {
    const N = api();
    if (N && N.permission === "default") void N.requestPermission();
  } catch {
    /* blocked by the browser; toasts still work */
  }
}

export function finishedText(c: CaseSummary): string {
  if (c.status === "FAILED") return `Case ${c.id} failed`;
  return `Case ${c.id} ready: ${(c.risk ?? "unknown").toUpperCase()} risk, ${c.findings_count ?? 0} findings`;
}

/** Show a system notification if the tab is in the background; true if one was shown. */
export function notifyFinished(c: CaseSummary, onClick: () => void): boolean {
  try {
    const N = api();
    if (!N || N.permission !== "granted" || document.visibilityState !== "hidden") return false;
    const n = new N(finishedText(c), { tag: `claimlens-${c.id}` });
    n.onclick = () => {
      onClick();
      n.close?.();
    };
    return true;
  } catch {
    return false;
  }
}
