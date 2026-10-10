import type { Case, CaseSummary, Finding, Status } from "./types";

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

    createCase(claim: File, policy: File) {
      const body = new FormData();
      body.append("claim", claim);
      body.append("policy", policy);
      return getJson<{ case_id: string; status: Status }>("/api/cases", { method: "POST", body });
    },

    review(id: string, fid: string, action: "accept" | "dismiss", note = "") {
      return getJson<Finding>(`/api/cases/${encodeURIComponent(id)}/findings/${encodeURIComponent(fid)}/review`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, note }),
      });
    },

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
