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

const card = (id: string, role: DraftCard["role"], files: File[] = [], kind: DraftCard["kind"] = null): DraftCard =>
  ({ id, role, kind, files });

test("case totals", () => {
  const policy = card("policy", "policy", [file("p.pdf")]);
  const bill = card("b1", "bill", [file("b.pdf")], "hospital");
  expect(checkCards([bill, policy])).toBeNull();
  expect(checkCards([bill, card("policy", "policy")])).toBe("Add the policy");
  expect(checkCards([card("b1", "bill", [], "hospital"), policy])).toBe("Add the claim documents");
  expect(checkCards([card("b1", "bill", Array.from({ length: 40 }, (_, i) => file(`${i}.pdf`)), "lab"), policy]))
    .toBe("At most 40 files");
  const bills = Array.from({ length: 11 }, (_, i) => card(`b${i}`, "bill", [file("b.pdf")], "other"));
  expect(checkCards([...bills, policy])).toBe("At most 10 bills");
});
