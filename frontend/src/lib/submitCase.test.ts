import { ApiError, type Client } from "../api/client";
import { submitCase, UploadFailed, type SubmitState } from "./submitCase";
import type { DraftCard } from "./upload";

const pdf = (name: string) => new File(["%PDF"], name);
const a = pdf("a.pdf"), b = pdf("b.pdf"), c = pdf("c.pdf"), p = pdf("p.pdf");
const cards: DraftCard[] = [
  { id: "claim", role: "claim", files: [a, b, c] },
  { id: "policy", role: "policy", files: [p] },
];

function fakeClient(failOn?: File) {
  const calls: string[] = [];
  const client = {
    createDraft: vi.fn(async (_cards: { id: string }[]) => { calls.push("draft"); return { case_id: "c1", status: "DRAFT" as const }; }),
    uploadFile: vi.fn(async (_id: string, card: string, file: File, _clientId: string) => {
      calls.push(`${card}/${file.name}`);
      if (file === failOn) throw new ApiError(400, "b1: not a readable PDF file");
      return { card_id: card, index: 0, pages: 1 };
    }),
    submit: vi.fn(async () => { calls.push("submit"); return { case_id: "c1", status: "QUEUED" as const }; }),
  };
  return { client: client as unknown as Client, raw: client, calls };
}

test("creates the draft, uploads every file in card order, then submits", async () => {
  const { client, calls } = fakeClient();
  const progress = vi.fn();
  const state: SubmitState = { uploaded: new Set() };
  expect(await submitCase(client, cards, state, progress)).toBe("c1");
  expect(calls).toEqual(["draft", "claim/a.pdf", "claim/b.pdf", "claim/c.pdf", "policy/p.pdf", "submit"]);
  expect(progress).toHaveBeenLastCalledWith(4, 4);
});

test("a failed file stops the run; a retry uploads only what is left", async () => {
  const first = fakeClient(c);
  const state: SubmitState = { uploaded: new Set() };
  await expect(submitCase(first.client, cards, state, vi.fn())).rejects.toEqual(
    new UploadFailed(c, "b1: not a readable PDF file"));
  expect(state.caseId).toBe("c1");

  const retry = fakeClient();
  await submitCase(retry.client, cards, state, vi.fn());
  expect(retry.calls).toEqual(["claim/c.pdf", "policy/p.pdf", "submit"]);
  expect(retry.raw.createDraft).not.toHaveBeenCalled();
});

test("every file carries one id, the same on a re-send", async () => {
  const first = fakeClient(c);
  const state: SubmitState = { uploaded: new Set() };
  await submitCase(first.client, cards, state, vi.fn()).catch(() => {});
  const retry = fakeClient();
  await submitCase(retry.client, cards, state, vi.fn());
  const idOf = (calls: unknown[][], f: File) => calls.find((call) => call[2] === f)![3];
  expect(idOf(retry.raw.uploadFile.mock.calls, c)).toBe(idOf(first.raw.uploadFile.mock.calls, c));
  expect(new Set(first.raw.uploadFile.mock.calls.map((call) => call[3])).size).toBe(3);
});

test("a submit that already went through (lost response, 409) still opens the case", async () => {
  const { client, raw } = fakeClient();
  raw.submit.mockRejectedValueOnce(new ApiError(409, "This case was already submitted"));
  expect(await submitCase(client, cards, { uploaded: new Set() }, vi.fn())).toBe("c1");
});
