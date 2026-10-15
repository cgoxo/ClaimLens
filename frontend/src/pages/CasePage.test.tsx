import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { Case } from "../api/types";
import { toPercentBox } from "../lib/highlight";
import { renderPage } from "../test/auth";
import { sampleCase } from "../test/sampleCase";
import CasePage from "./CasePage";

function setup(overrides: Record<string, unknown> = {}, data: Case = sampleCase) {
  const client = {
    getCase: vi.fn(async () => data),
    pageImageUrl: vi.fn(async () => "blob:x"),
    releaseImages: vi.fn(),
    review: vi.fn(async (_id: string, fid: string, action: "accept" | "dismiss") => ({
      ...data.findings.find((f) => f.id === fid)!,
      review: { action, note: "", by: "a@x.com", at: "2026-10-10T10:00:00Z" },
    })),
    ...overrides,
  };
  renderPage(<CasePage />, client, "/cases/c1", "/cases/:id");
  return client;
}

const card = (title: RegExp) => screen.getByRole("button", { name: title }).closest("article")!;

test("shows the stamp, payable and grouped findings", async () => {
  setup();
  expect(await screen.findByLabelText("Risk high, score 100 of 100")).toBeInTheDocument();
  expect(screen.getByText("₹0")).toBeInTheDocument();
  for (const h of ["Critical (3)", "High (3)", "Low (1)", "Coverage (2)"])
    expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
  expect(screen.getAllByRole("article")).toHaveLength(9);
});

test("selecting a page finding opens its page with a marker at the cited box", async () => {
  setup();
  await userEvent.click(await screen.findByRole("button", { name: /Amount in a different font/ }));
  expect(screen.getByRole("tab", { name: "Claim" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("button", { name: "claim page 3" })).toHaveAttribute("aria-current", "true");
  const marker = await screen.findByTestId("marker");
  const f = sampleCase.findings.find((x) => x.code === "font_outlier")!;
  const page = sampleCase.pages.find((p) => p.doc === "claim" && p.page === 3)!;
  const expected = toPercentBox(f.citations[0].bbox!, page.width, page.height);
  expect(parseFloat(marker.style.left)).toBeCloseTo(expected.left, 1);
});

test("a metadata finding shows the file properties banner and no marker", async () => {
  setup();
  await userEvent.click(await screen.findByRole("button", { name: /saved with an editing tool/ }));
  expect(screen.getByText(/File properties/)).toBeInTheDocument();
  expect(screen.queryByTestId("marker")).toBeNull();
});

test("a citation without a box shows the quoted text and no marker", async () => {
  setup();
  await userEvent.click(await screen.findByRole("button", { name: /waiting period/ }));
  expect(screen.getByRole("tab", { name: "Policy" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText(/Quoted text:/)).toBeInTheDocument();
  expect(screen.queryByTestId("marker")).toBeNull();
});

test("j and k move between findings", async () => {
  setup();
  await screen.findAllByRole("article");
  const cards = screen.getAllByRole("article");
  expect(cards[0]).toHaveAttribute("aria-current", "true");
  fireEvent.keyDown(document, { key: "j" });
  expect(cards[1]).toHaveAttribute("aria-current", "true");
  fireEvent.keyDown(document, { key: "k" });
  expect(cards[0]).toHaveAttribute("aria-current", "true");
});

test("accept saves the review and shows who accepted", async () => {
  const client = setup();
  await screen.findAllByRole("article");
  const target = within(card(/Amount in a different font/));
  await userEvent.click(target.getByRole("button", { name: "Accept" }));
  expect(client.review).toHaveBeenCalledWith("c1", "font_outlier-claim-3-1", "accept", "");
  expect(await target.findByText(/Accepted by a@x.com/)).toBeInTheDocument();
});

test("a failed review reverts and shows an error", async () => {
  setup({ review: vi.fn(async () => { throw new ApiError(500, "boom"); }) });
  await screen.findAllByRole("article");
  const target = within(card(/Amount in a different font/));
  await userEvent.click(target.getByRole("button", { name: "Accept" }));
  expect(await target.findByText(/Couldn't save the review/)).toBeInTheDocument();
  expect(target.queryByText(/Accepted by/)).toBeNull();
});

test("a running case shows the progress line", async () => {
  setup({}, { ...sampleCase, status: "CHECKING", findings: [], score: null, risk: null });
  const current = await screen.findByText("Checking");
  expect(current.closest("li")).toHaveAttribute("aria-current", "step");
});

test("a failed case shows the step, error and a way back", async () => {
  setup({}, { ...sampleCase, status: "FAILED", step: "CHECKING", error: "AI returned no output", findings: [] });
  expect(await screen.findByText(/AI returned no output/)).toBeInTheDocument();
  expect(screen.getByText(/CHECKING/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to upload" })).toHaveAttribute("href", "/");
});

test("a missing case says so", async () => {
  setup({ getCase: vi.fn(async () => { throw new ApiError(404, "Case not found"); }) });
  expect(await screen.findByRole("heading", { name: "Case not found" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Back to upload/ })).toHaveAttribute("href", "/");
});

test("a page image that fails to load can be retried", async () => {
  const pageImageUrl = vi.fn().mockRejectedValueOnce(new Error("net")).mockResolvedValue("blob:x");
  setup({ pageImageUrl });
  expect(await screen.findByText("Couldn't load page 3")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(screen.queryByText("Couldn't load page 3")).toBeNull());
  expect(pageImageUrl).toHaveBeenCalledTimes(2);
});

test("review actions show only on the selected card", async () => {
  setup();
  await screen.findAllByRole("article");
  const second = within(card(/Hidden text under a white box/));
  expect(second.queryByRole("button", { name: "Accept" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: /Hidden text under a white box/ }));
  expect(second.getByRole("button", { name: "Accept" })).toBeInTheDocument();
});

test("the score is shown once, on the stamp", async () => {
  setup();
  await screen.findByLabelText("Risk high, score 100 of 100");
  expect(screen.queryByText("Score")).toBeNull();
});

test("selecting the current finding again returns the viewer to its page", async () => {
  setup();
  await userEvent.click(await screen.findByRole("button", { name: /Amount in a different font/ }));
  await userEvent.click(screen.getByRole("tab", { name: "Policy" }));
  await userEvent.click(screen.getByRole("button", { name: /Amount in a different font/ }));
  expect(screen.getByRole("tab", { name: "Claim" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("button", { name: "claim page 3" })).toHaveAttribute("aria-current", "true");
});

test("leaving the case page releases its page images", async () => {
  const releaseImages = vi.fn();
  const { unmount } = renderPage(<CasePage />, {
    getCase: vi.fn(async () => sampleCase), pageImageUrl: vi.fn(async () => "blob:x"), releaseImages,
  }, "/cases/c1", "/cases/:id");
  await screen.findAllByRole("article");
  unmount();
  expect(releaseImages).toHaveBeenCalled();
});

test("while checking, shows progress, the context panel and the viewer", async () => {
  setup({}, { ...sampleCase, status: "CHECKING", findings: [], risk: null, score: null,
    progress: { step: "CHECKING", done: 1, total: 4, label: "Checking: story" } });
  expect(await screen.findByText("Checking: story")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "The claim" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Claim" })).toBeInTheDocument();
});

test("a context link opens its page in the viewer", async () => {
  setup();
  await userEvent.click(await screen.findByRole("button", { name: "Diagnosis, claim page 2" }));
  expect(screen.getByRole("button", { name: "claim page 2" })).toHaveAttribute("aria-current", "true");
});

test("opening a finished case refreshes the case list so its new badge clears", async () => {
  const listCases = vi.fn(async () => []);
  setup({ listCases });
  await screen.findByLabelText("Risk high, score 100 of 100");
  await waitFor(() => expect(listCases).toHaveBeenCalledTimes(2));
});

test("a rejected case says which files stopped it and why", async () => {
  setup({}, { ...sampleCase, status: "REJECTED", findings: [], risk: null, score: null, context: null,
    rejected: [{ name: "resume.pdf", form: "Claim", reason: "This is a CV, not an insurance document.", page: 5,
      quote: "Curriculum Vitae" }] });
  expect(await screen.findByRole("heading", { name: "This claim can't be analysed" })).toBeInTheDocument();
  expect(screen.getByText("resume.pdf")).toBeInTheDocument();
  expect(screen.getByText(/This is a CV, not an insurance document\./)).toBeInTheDocument();
  expect(screen.getByText(/Curriculum Vitae/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Start a new case" })).toHaveAttribute("href", "/");
});
