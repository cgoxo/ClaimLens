export type UploadKind = "claim" | "policy";

const MAX_MB = 20;
const ALLOWED: Record<UploadKind, { exts: string[]; message: string }> = {
  claim: { exts: ["pdf", "jpg", "jpeg", "png"], message: "Claim must be a PDF, JPG or PNG" },
  policy: { exts: ["pdf"], message: "Policy must be a PDF" },
};

/** Same rules as the backend, so most mistakes are caught before upload. */
export function checkFile(kind: UploadKind, file: File): string | null {
  const ext = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!ALLOWED[kind].exts.includes(ext)) return ALLOWED[kind].message;
  if (file.size > MAX_MB * 1024 * 1024) return `File is larger than ${MAX_MB} MB`;
  return null;
}
