import { checkCards, checkFile, type DraftCard } from "./upload";

const file = (name: string, size = 10) => {
  const f = new File(["x"], name);
  Object.defineProperty(f, "size", { value: size });
  return f;
};

test("any card accepts pdf, jpg, png in any case", () => {
  for (const name of ["x.PNG", "x.pdf", "x.jpeg", "x.jpg"]) expect(checkFile(file(name))).toBeNull();
  expect(checkFile(file("x.docx"))).toBe("Must be a PDF, JPG or PNG");
});

test("rejects files over 20 MB", () => {
  expect(checkFile(file("x.pdf", 21 * 1024 * 1024))).toBe("File is larger than 20 MB");
});

const card = (id: string, role: DraftCard["role"], files: File[] = []): DraftCard => ({ id, role, files });

test("case totals", () => {
  const policy = card("policy", "policy", [file("p.pdf")]);
  const claim = card("claim", "claim", [file("b.pdf")]);
  expect(checkCards([claim, policy])).toBeNull();
  expect(checkCards([claim, card("policy", "policy")])).toBe("Add the policy");
  expect(checkCards([card("claim", "claim"), policy])).toBe("Add the claim documents");
  expect(checkCards([card("claim", "claim", Array.from({ length: 40 }, (_, i) => file(`${i}.pdf`))), policy]))
    .toBe("At most 40 files");
});
