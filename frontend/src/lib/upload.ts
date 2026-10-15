import type { CardSpec } from "../api/types";

const MAX_MB = 20;
const MAX_FILES = 40;
const MAX_BILLS = 10;
const EXTS = ["pdf", "jpg", "jpeg", "png"];

/** A card being filled in on the upload page. */
export type DraftCard = CardSpec & { files: File[] };

/** Same rules as the backend, so most mistakes are caught before upload. */
export function checkFile(file: File): string | null {
  const ext = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!EXTS.includes(ext)) return "Must be a PDF, JPG or PNG";
  if (file.size > MAX_MB * 1024 * 1024) return `File is larger than ${MAX_MB} MB`;
  return null;
}

/** The case-wide rules (page counts are only known after upload; the server checks those). */
export function checkCards(cards: DraftCard[]): string | null {
  if (cards.filter((c) => c.role === "bill").length > MAX_BILLS) return `At most ${MAX_BILLS} bills`;
  if (!cards.some((c) => c.role === "policy" && c.files.length)) return "Add the policy";
  if (!cards.some((c) => c.role !== "policy" && c.files.length)) return "Add the claim documents";
  if (cards.reduce((n, c) => n + c.files.length, 0) > MAX_FILES) return `At most ${MAX_FILES} files`;
  return null;
}
