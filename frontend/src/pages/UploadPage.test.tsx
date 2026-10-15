import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import { renderPage } from "../test/auth";
import UploadPage from "./UploadPage";

const pdf = (name: string) => new File(["%PDF-1.4"], name, { type: "application/pdf" });
const user = () => userEvent.setup({ applyAccept: false });

function setup(overrides = {}) {
  const client = {
    listCases: vi.fn(async () => [
      { id: "old1", status: "READY" as const, risk: "low" as const, score: 5, created_at: "2026-10-09T10:00:00Z", progress: null, findings_count: 1, unseen: false },
      { id: "new1", status: "READY" as const, risk: "high" as const, score: 100, created_at: "2026-10-10T10:00:00Z", progress: null, findings_count: 9, unseen: false },
    ]),
    createCase: vi.fn(async () => ({ case_id: "c1", status: "QUEUED" as const })),
    ...overrides,
  };
  renderPage(<UploadPage />, client);
  return client;
}

test("Open case is disabled until both trays have valid files", async () => {
  setup();
  const open = screen.getByRole("button", { name: "Open case" });
  expect(open).toBeDisabled();
  await user().upload(screen.getByLabelText("Claim file"), pdf("claim.pdf"));
  expect(open).toBeDisabled();
  await user().upload(screen.getByLabelText("Policy file"), pdf("policy.pdf"));
  expect(open).toBeEnabled();
});

test("a wrong claim type shows the message", async () => {
  setup();
  await user().upload(screen.getByLabelText("Claim file"), new File(["x"], "claim.docx"));
  expect(screen.getByText("Claim must be a PDF, JPG or PNG")).toBeInTheDocument();
});

test("submitting creates the case and opens it", async () => {
  const client = setup();
  await user().upload(screen.getByLabelText("Claim file"), pdf("claim.pdf"));
  await user().upload(screen.getByLabelText("Policy file"), pdf("policy.pdf"));
  await user().click(screen.getByRole("button", { name: "Open case" }));
  expect(client.createCase).toHaveBeenCalledTimes(1);
  expect(await screen.findByText("case page c1")).toBeInTheDocument();
});

test("a backend rejection shows its message and keeps the files", async () => {
  setup({ createCase: vi.fn(async () => { throw new ApiError(400, "claim: not a readable PDF file"); }) });
  await user().upload(screen.getByLabelText("Claim file"), pdf("claim.pdf"));
  await user().upload(screen.getByLabelText("Policy file"), pdf("policy.pdf"));
  await user().click(screen.getByRole("button", { name: "Open case" }));
  expect(await screen.findByText("claim: not a readable PDF file")).toBeInTheDocument();
  expect(screen.getByText("claim.pdf")).toBeInTheDocument();
  expect(screen.getByText("policy.pdf")).toBeInTheDocument();
});

test("Try the sample fetches both sample files and opens the case", async () => {
  const fetchMock = vi.fn(async (_url: string) => new Response(new Blob(["%PDF"]), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const client = setup();
  await user().click(screen.getByRole("button", { name: /Try the sample/ }));
  expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(["/samples/claim.pdf", "/samples/policy.pdf"]);
  const [claim, policy] = client.createCase.mock.calls[0] as unknown as [File, File];
  expect([claim.name, policy.name]).toEqual(["claim.pdf", "policy.pdf"]);
  expect(await screen.findByText("case page c1")).toBeInTheDocument();
  vi.unstubAllGlobals();
});

test("Your cases lists cases newest first, linking to each", async () => {
  setup();
  await waitFor(() => expect(screen.getAllByRole("link", { name: /new1|old1/ })).toHaveLength(2));
  const links = screen.getAllByRole("link", { name: /new1|old1/ });
  expect(links[0]).toHaveAttribute("href", "/cases/new1");
  expect(links[1]).toHaveAttribute("href", "/cases/old1");
});
