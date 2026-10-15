import { ApiError, createClient } from "./client";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const client = (onUnauthorized = vi.fn()) =>
  createClient(async () => ({ "X-Dev-User": "a@x.com" }), onUnauthorized);

test("sends the auth headers on every call", async () => {
  fetchMock.mockResolvedValue(json(200, { email: "a@x.com" }));
  await client().me();
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/me");
  expect(new Headers(init.headers).get("X-Dev-User")).toBe("a@x.com");
});

test("non-2xx becomes ApiError with status and detail", async () => {
  fetchMock.mockResolvedValue(json(400, { detail: "claim: not a readable PDF file" }));
  await expect(client().getCase("c1")).rejects.toMatchObject({ status: 400, detail: "claim: not a readable PDF file" });
  fetchMock.mockResolvedValue(json(400, { detail: "x" }));
  await expect(client().getCase("c1")).rejects.toBeInstanceOf(ApiError);
});

test("401 calls onUnauthorized once and throws", async () => {
  const onUnauthorized = vi.fn();
  fetchMock.mockResolvedValue(json(401, { detail: "Sign in required" }));
  await expect(client(onUnauthorized).listCases()).rejects.toMatchObject({ status: 401 });
  expect(onUnauthorized).toHaveBeenCalledTimes(1);
});

test("createDraft posts the cards as JSON", async () => {
  fetchMock.mockResolvedValue(json(201, { case_id: "c1", status: "DRAFT" }));
  const cards = [{ id: "b1", role: "bill" as const, kind: "hospital" as const }];
  expect(await client().createDraft(cards)).toEqual({ case_id: "c1", status: "DRAFT" });
  const [url, init] = fetchMock.mock.calls[0];
  expect([url, init.method]).toEqual(["/api/cases", "POST"]);
  expect(JSON.parse(init.body)).toEqual({ cards });
  expect(new Headers(init.headers).get("content-type")).toBe("application/json");
});

test("uploadFile posts one file with its card", async () => {
  fetchMock.mockResolvedValue(json(201, { card_id: "b1", index: 0, pages: 2 }));
  const file = new File(["%PDF"], "bill.pdf");
  expect(await client().uploadFile("c1", "b1", file)).toEqual({ card_id: "b1", index: 0, pages: 2 });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/cases/c1/files");
  expect((init.body as FormData).get("card_id")).toBe("b1");
  expect(((init.body as FormData).get("file") as File).name).toBe("bill.pdf");
  expect(new Headers(init.headers).has("content-type")).toBe(false);
});

test("submit posts to submit", async () => {
  fetchMock.mockResolvedValue(json(200, { case_id: "c1", status: "QUEUED" }));
  expect(await client().submit("c1")).toEqual({ case_id: "c1", status: "QUEUED" });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/cases/c1/submit");
});

test("review posts the action and note", async () => {
  fetchMock.mockResolvedValue(json(200, { id: "f1" }));
  await client().review("c1", "f1", "dismiss", "typo");
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/cases/c1/findings/f1/review");
  expect(JSON.parse(init.body)).toEqual({ action: "dismiss", note: "typo" });
});

test("pageImageUrl returns a cached object URL", async () => {
  const createObjectURL = vi.fn(() => "blob:page");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL }));
  fetchMock.mockResolvedValue(new Response(new Blob(["png"]), { status: 200 }));
  const c = client();
  expect(await c.pageImageUrl("c1", "claim", 3)).toBe("blob:page");
  expect(await c.pageImageUrl("c1", "claim", 3)).toBe("blob:page");
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/cases/c1/pages/claim/3.png");
});

test("concurrent requests for one page share a single object URL, and release revokes it", async () => {
  const createObjectURL = vi.fn(() => "blob:page");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL }));
  fetchMock.mockImplementation(async () => new Response(new Blob(["png"]), { status: 200 }));
  const c = client();
  await Promise.all([c.pageImageUrl("c1", "claim", 1), c.pageImageUrl("c1", "claim", 1)]);
  expect(createObjectURL).toHaveBeenCalledTimes(1);
  c.releaseImages();
  await vi.waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:page"));
});

test("a 401 releases cached page images", async () => {
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:p"), revokeObjectURL }));
  fetchMock.mockResolvedValueOnce(new Response(new Blob(["png"]), { status: 200 }));
  const c = client();
  await c.pageImageUrl("c1", "claim", 1);
  fetchMock.mockResolvedValueOnce(json(401, { detail: "expired" }));
  await c.listCases().catch(() => {});
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:p");
});
