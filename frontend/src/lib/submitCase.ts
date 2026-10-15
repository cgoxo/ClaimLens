import { ApiError, type Client } from "../api/client";
import type { DraftCard } from "./upload";

/** Kept by the upload page between attempts, so a retry continues instead of starting over. */
export interface SubmitState {
  caseId?: string;
  uploaded: Set<File>;
  /** one id per file, kept across attempts: a re-send after a lost response is recognised by the server */
  ids?: Map<File, string>;
}

export class UploadFailed extends Error {
  constructor(public file: File, message: string) {
    super(message);
    this.name = "UploadFailed";
  }
}

/** Create the draft (once), upload each file not yet uploaded in card order, then submit. Returns the case id. */
export async function submitCase(client: Client, cards: DraftCard[], state: SubmitState,
  onProgress: (done: number, total: number) => void): Promise<string> {
  const filled = cards.filter((c) => c.files.length);
  if (!state.caseId) {
    const { case_id } = await client.createDraft(filled.map(({ id, role }) => ({ id, role })));
    state.caseId = case_id;
  }
  const ids = (state.ids ??= new Map());
  const all = filled.flatMap((c) => c.files.map((file) => ({ card: c.id, file })));
  for (const { file } of all) if (!ids.has(file)) ids.set(file, crypto.randomUUID());
  onProgress(all.filter((f) => state.uploaded.has(f.file)).length, all.length);
  for (const { card, file } of all) {
    if (state.uploaded.has(file)) continue;
    try {
      await client.uploadFile(state.caseId, card, file, ids.get(file)!);
    } catch (e) {
      throw new UploadFailed(file, e instanceof ApiError ? e.detail : e instanceof Error ? e.message : "Upload failed");
    }
    state.uploaded.add(file);
    onProgress(all.filter((f) => state.uploaded.has(f.file)).length, all.length);
  }
  try {
    await client.submit(state.caseId);
  } catch (e) {
    // 409: an earlier submit got through and only its response was lost
    if (!(e instanceof ApiError && e.status === 409)) throw e;
  }
  return state.caseId;
}
