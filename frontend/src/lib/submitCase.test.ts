import { ApiError, type Client } from "../api/client";
import { submitCase, UploadFailed, type SubmitState } from "./submitCase";
import type { DraftCard } from "./upload";

const pdf = (name: string) => new File(["%PDF"], name);
const a = pdf("a.pdf"), b = pdf("b.pdf"), c = pdf("c.pdf"), p = pdf("p.pdf");
const cards: DraftCard[] = [
  { id: "claim-form", role: "claim_form", kind: null, files: [a] },
  { id: "b1", role: "bill", kind: "hospital", files: [b, c] },
  { id: "supporting", role: "supporting", kind: null, files: [] },
  { id: "policy", role: "policy", kind: null, files: [p] },
];

function fakeClient(failOn?: File) {
  const calls: string[] = [];
  const client = {
    createDraft: vi.fn(async (_cards: { id: string }[]) => { calls.push("draft"); return { case_id: "c1", status: "DRAFT" as const }; }),
    uploadFile: vi.fn(async (_id: string, card: string, file: File) => {
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
  expect(calls).toEqual(["draft", "claim-form/a.pdf", "b1/b.pdf", "b1/c.pdf", "policy/p.pdf", "submit"]);
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
  expect(retry.calls).toEqual(["b1/c.pdf", "policy/p.pdf", "submit"]);
  expect(retry.raw.createDraft).not.toHaveBeenCalled();
});

test("empty cards are not sent", async () => {
  const { raw, client } = fakeClient();
  await submitCase(client, cards, { uploaded: new Set() }, vi.fn());
  expect(raw.createDraft.mock.calls[0][0].map((card: { id: string }) => card.id)).toEqual(["claim-form", "b1", "policy"]);
});
