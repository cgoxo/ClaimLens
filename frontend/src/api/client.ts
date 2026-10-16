import type { Box, CardSpec, Case, CaseSummary, ChatMessage, ChatState, ChatThread, Finding, Outcome, Proposal, Status } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

type Headers = Record<string, string>;

export function createClient(getHeaders: () => Promise<Headers>, onUnauthorized: () => void) {
  const images = new Map<string, Promise<string>>();

  async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers({ ...(await getHeaders()), ...(init.headers as Headers | undefined) });
    const res = await fetch(path, { ...init, headers });
    if (res.ok) return res;
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401) {
      releaseImages();
      onUnauthorized();
    }
    throw new ApiError(res.status, detail);
  }

  function releaseImages() {
    images.forEach((p) => void p.then((url) => URL.revokeObjectURL(url), () => {}));
    images.clear();
  }

  const getJson = async <T>(path: string, init?: RequestInit) => (await request(path, init)).json() as Promise<T>;

  return {
    me: () => getJson<{ email: string }>("/api/me"),
    listCases: () => getJson<CaseSummary[]>("/api/cases"),
    getCase: (id: string) => getJson<Case>(`/api/cases/${encodeURIComponent(id)}`),

    /** Step 1 of 3: a draft case with its cards. */
    createDraft(cards: CardSpec[]) {
      return getJson<{ case_id: string; status: Status }>("/api/cases", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ cards }),
      });
    },

    /** Step 2 of 3: one file into one card (one per request: Cloud Run caps a request at 32 MB). */
    uploadFile(caseId: string, cardId: string, file: File, clientId: string) {
      const body = new FormData();
      body.append("card_id", cardId);
      body.append("client_id", clientId); // the same id on a re-send, so the server keeps the file once
      body.append("file", file);
      return getJson<{ card_id: string; index: number; pages: number }>(
        `/api/cases/${encodeURIComponent(caseId)}/files`, { method: "POST", body });
    },

    /** Step 3 of 3: queue the analysis. */
    submit(caseId: string) {
      return getJson<{ case_id: string; status: Status }>(`/api/cases/${encodeURIComponent(caseId)}/submit`,
        { method: "POST" });
    },

    review(id: string, fid: string, action: "accept" | "dismiss" | "restore", note = "") {
      return getJson<Finding & { current?: Outcome | null }>(`/api/cases/${encodeURIComponent(id)}/findings/${encodeURIComponent(fid)}/review`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, note }),
      });
    },

    getChat: (id: string) => getJson<ChatState>(`/api/cases/${encodeURIComponent(id)}/chat`),

    ask(id: string, text: string, selection?: Box | null) {
      return getJson<ChatMessage>(`/api/cases/${encodeURIComponent(id)}/chat/messages`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(selection ? { text, selection } : { text }),
      });
    },

    newChat: (id: string) => getJson<ChatThread>(`/api/cases/${encodeURIComponent(id)}/chat/new`, { method: "POST" }),

    decide: (id: string, pid: string, decision: "apply" | "ignore") =>
      getJson<{ proposal: Proposal; current: Outcome | null }>(
        `/api/cases/${encodeURIComponent(id)}/chat/proposals/${encodeURIComponent(pid)}/${decision}`, { method: "POST" }),

    /** Page images need the auth header, so they are fetched and shown as object URLs. */
    pageImageUrl(id: string, doc: string, n: number): Promise<string> {
      const key = `${id}/${doc}/${n}`;
      // cache the promise, so concurrent requests for one page share a single fetch and object URL
      let pending = images.get(key);
      if (!pending) {
        pending = request(`/api/cases/${encodeURIComponent(id)}/pages/${doc}/${n}.png`)
          .then(async (res) => URL.createObjectURL(await res.blob()));
        pending.catch(() => images.delete(key));
        images.set(key, pending);
      }
      return pending;
    },

    releaseImages,
  };
}

export type Client = ReturnType<typeof createClient>;
