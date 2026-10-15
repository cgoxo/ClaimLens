import { ApiError, type Client } from "../api/client";
import type { DraftCard } from "./upload";

/** Kept by the upload page between attempts, so a retry continues instead of starting over. */
export interface SubmitState {
  caseId?: string;
  uploaded: Set<File>;
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
    const { case_id } = await client.createDraft(filled.map(({ id, role, kind }) => ({ id, role, kind })));
    state.caseId = case_id;
  }
  const all = filled.flatMap((c) => c.files.map((file) => ({ card: c.id, file })));
  onProgress(all.filter((f) => state.uploaded.has(f.file)).length, all.length);
  for (const { card, file } of all) {
    if (state.uploaded.has(file)) continue;
    try {
      await client.uploadFile(state.caseId, card, file);
    } catch (e) {
      throw new UploadFailed(file, e instanceof ApiError ? e.detail : e instanceof Error ? e.message : "Upload failed");
    }
    state.uploaded.add(file);
    onProgress(all.filter((f) => state.uploaded.has(f.file)).length, all.length);
  }
  await client.submit(state.caseId);
  return state.caseId;
}
