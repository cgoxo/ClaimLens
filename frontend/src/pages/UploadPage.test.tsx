import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import { askPermission } from "../lib/notify";
import { renderPage } from "../test/auth";
import UploadPage from "./UploadPage";

vi.mock("../lib/notify", async (original) => ({
  ...(await original<typeof import("../lib/notify")>()),
  askPermission: vi.fn(),
}));

const pdf = (name: string) => new File(["%PDF-1.4"], name, { type: "application/pdf" });
const user = () => userEvent.setup();

function setup(overrides = {}) {
  const client = {
    listCases: vi.fn(async () => [
      { id: "old1", status: "READY" as const, risk: "low" as const, score: 5, created_at: "2026-10-09T10:00:00Z",
        progress: null, findings_count: 1, unseen: false },
      { id: "new1", status: "READY" as const, risk: "high" as const, score: 100, created_at: "2026-10-10T10:00:00Z",
        progress: null, findings_count: 9, unseen: false },
    ]),
    createDraft: vi.fn(async (_cards: { id: string; kind: string | null }[]) => ({ case_id: "c1", status: "DRAFT" as const })),
    uploadFile: vi.fn(async (_c: string, card_id: string, _f: File) => ({ card_id, index: 0, pages: 1 })),
    submit: vi.fn(async () => ({ case_id: "c1", status: "QUEUED" as const })),
    ...overrides,
  };
  renderPage(<UploadPage />, client);
  return client;
}

async function fillClaimAndPolicy() {
  await user().upload(screen.getByLabelText("Add files to Bill 1"), pdf("bill.pdf"));
  await user().upload(screen.getByLabelText("Add files to Policy"), pdf("policy.pdf"));
}

test("Open case is disabled until there is a claim document and a policy", async () => {
  setup();
  const open = screen.getByRole("button", { name: "Open case" });
  expect(open).toBeDisabled();
  await user().upload(screen.getByLabelText("Add files to Bill 1"), pdf("bill.pdf"));
  expect(open).toBeDisabled();
  await user().upload(screen.getByLabelText("Add files to Policy"), pdf("policy.pdf"));
  expect(open).toBeEnabled();
});

test("opening a case uploads the cards, asks to notify, and opens the case", async () => {
  const client = setup();
  await fillClaimAndPolicy();
  await user().click(screen.getByRole("button", { name: "Open case" }));
  expect(await screen.findByText("case page c1")).toBeInTheDocument();
  expect(askPermission).toHaveBeenCalled();
  expect(client.uploadFile.mock.calls.map((c) => c[1])).toEqual(["b1", "policy"]);
  expect(client.submit).toHaveBeenCalledWith("c1");
});

test("a rejected file shows its message, and retrying sends only the rest", async () => {
  const uploadFile = vi.fn()
    .mockResolvedValueOnce({ card_id: "b1", index: 0, pages: 1 })
    .mockRejectedValueOnce(new ApiError(400, "policy: not a readable PDF file"))
    .mockResolvedValue({ card_id: "policy", index: 0, pages: 1 });
  const client = setup({ uploadFile });
  await fillClaimAndPolicy();
  await user().click(screen.getByRole("button", { name: "Open case" }));
  expect(await screen.findByText("policy: not a readable PDF file")).toBeInTheDocument();
  await user().click(screen.getByRole("button", { name: "Open case" }));
  expect(await screen.findByText("case page c1")).toBeInTheDocument();
  expect(client.createDraft).toHaveBeenCalledTimes(1);
  expect(uploadFile.mock.calls.map((c) => c[2].name)).toEqual(["bill.pdf", "policy.pdf", "policy.pdf"]);
});

test("Try the sample uploads the five sample files into their cards", async () => {
  const fetchMock = vi.fn(async (_url: string) => new Response(new Blob(["%PDF"]), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const client = setup();
  await user().click(screen.getByRole("button", { name: /Try the sample/ }));
  expect(await screen.findByText("case page c1")).toBeInTheDocument();
  expect(client.createDraft.mock.calls[0][0].map((c: { id: string; kind: string | null }) => [c.id, c.kind])).toEqual([
    ["claim-form", null], ["b1", "hospital"], ["b2", "pharmacy"], ["supporting", null], ["policy", null]]);
  expect(client.uploadFile.mock.calls.map((c) => [c[1], c[2].name])).toEqual([
    ["claim-form", "claim-form.pdf"], ["b1", "hospital-bill.pdf"], ["b2", "pharmacy-bill.jpg"],
    ["supporting", "discharge-summary.pdf"], ["policy", "policy.pdf"]]);
  vi.unstubAllGlobals();
});

test("Your cases lists cases newest first, linking to each", async () => {
  setup();
  await waitFor(() => expect(screen.getAllByRole("link", { name: /new1|old1/ })).toHaveLength(2));
  const links = screen.getAllByRole("link", { name: /new1|old1/ });
  expect(links[0]).toHaveAttribute("href", "/cases/new1");
  expect(links[1]).toHaveAttribute("href", "/cases/old1");
});
