import { checkFile } from "./upload";

const file = (name: string, size = 10) => {
  const f = new File(["x"], name);
  Object.defineProperty(f, "size", { value: size });
  return f;
};

test("claim accepts pdf, jpg, png in any case", () => {
  expect(checkFile("claim", file("x.PNG"))).toBeNull();
  expect(checkFile("claim", file("x.pdf"))).toBeNull();
  expect(checkFile("claim", file("x.docx"))).toBe("Claim must be a PDF, JPG or PNG");
});

test("policy must be a pdf", () => {
  expect(checkFile("policy", file("x.jpg"))).toBe("Policy must be a PDF");
});

test("rejects files over 20 MB", () => {
  expect(checkFile("claim", file("x.pdf", 21 * 1024 * 1024))).toBe("File is larger than 20 MB");
});
