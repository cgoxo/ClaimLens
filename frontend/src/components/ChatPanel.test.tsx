import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { Client } from "../api/client";
import type { ChatState } from "../api/types";
import { cite, message, proposal } from "../test/chat";
import { outcome } from "../test/outcome";
import ChatPanel from "./ChatPanel";

const empty: ChatState = { thread: null, messages: [], previous: [] };
const thread = { id: "t1", status: "active" as const, carried_summary: "", summary: "", created_by: "a@x.com", created_at: "2026-10-16T10:00:00Z" };

function setup(state: ChatState = empty, extra: Record<string, unknown> = {}, props: Record<string, unknown> = {}) {
  const client = { getChat: vi.fn(async () => state), ask: vi.fn(async () => message()), newChat: vi.fn(async () => thread),
    decide: vi.fn(async () => ({ proposal: proposal({ status: "applied" }), current: outcome() })), ...extra };
  const onOpenCitation = vi.fn(), onOutcome = vi.fn(), onClearSelection = vi.fn();
  render(<ChatPanel caseId="c1" client={client as unknown as Client} onOpenCitation={onOpenCitation}
    onOutcome={onOutcome} pendingSelection={null} onClearSelection={onClearSelection} {...props} />);
  return { client, onOpenCitation, onOutcome, onClearSelection };
}

const withMessages = (...messages: ChatState["messages"]): ChatState => ({ thread, messages, previous: [] });

test("with no thread yet it shows the empty chat and the text box", async () => {
  setup();
  expect(await screen.findByRole("textbox")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
});

test("renders messages and a citation chip opens the page", async () => {
  const { onOpenCitation } = setup(withMessages(message({ id: "m0", role: "reviewer", text: "What is the total?", citations: [] }), message()));
  expect(await screen.findByText("What is the total?")).toBeInTheDocument();
  expect(screen.getByText("The total is Rs 48,500.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /claim p\.3/ }));
  expect(onOpenCitation).toHaveBeenCalledWith(cite);
});

test("an unverified answer is muted and says so; notes show", async () => {
  setup(withMessages(message({ verified: false, citations: [], notes: ["A proposal was dropped."] })));
  expect(await screen.findByText("Couldn't verify against the documents")).toBeInTheDocument();
  expect(screen.getByText("The total is Rs 48,500.").closest("article")).toHaveClass("is-unverified");
  expect(screen.getByText("A proposal was dropped.")).toBeInTheDocument();
});

test("sending shows Thinking… with Send disabled, then the reply", async () => {
  let finish!: (m: ReturnType<typeof message>) => void;
  const ask = vi.fn(() => new Promise<ReturnType<typeof message>>((r) => { finish = r; }));
  setup(empty, { ask });
  await userEvent.type(await screen.findByRole("textbox"), "Hi there");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Thinking…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  expect(ask).toHaveBeenCalledWith("c1", "Hi there", null);
  expect(screen.getByRole("article")).toHaveTextContent("Hi there");
  finish(message());
  expect(await screen.findByText("The total is Rs 48,500.")).toBeInTheDocument();
  expect(screen.queryByText("Thinking…")).toBeNull();
  expect(screen.getByRole("textbox")).toHaveValue("");
});

test("an error shows the message and keeps the text", async () => {
  setup(empty, { ask: vi.fn(async () => { throw new ApiError(503, "Couldn't answer right now, try again"); }) });
  await userEvent.type(await screen.findByRole("textbox"), "Hi there");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Couldn't answer right now, try again")).toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("Hi there");
  expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
});

test("a 400 shows its own reason", async () => {
  setup(empty, { ask: vi.fn(async () => { throw new ApiError(400, "The selected box has no size"); }) });
  await userEvent.type(await screen.findByRole("textbox"), "x");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("The selected box has no size")).toBeInTheDocument();
});

test("a pending selection is sent and cleared", async () => {
  const box = { doc: "claim", page: 2, bbox: [1, 1, 5, 5] as [number, number, number, number] };
  const { client, onClearSelection } = setup(empty, {}, { pendingSelection: box });
  await userEvent.type(await screen.findByRole("textbox"), "What is this?");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(client.ask).toHaveBeenCalledWith("c1", "What is this?", box);
  await waitFor(() => expect(onClearSelection).toHaveBeenCalled());
});

test("Apply calls decide then onOutcome; the card shows Applied", async () => {
  const { client, onOutcome } = setup(withMessages(message({ proposals: [proposal()] })),
    {}, { findings: [{ id: "f1", title: "Edited total" }] });
  expect(await screen.findByText("Dismiss: Edited total")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(client.decide).toHaveBeenCalledWith("c1", "p1", "apply");
  await waitFor(() => expect(onOutcome).toHaveBeenCalledWith(expect.objectContaining({ risk: outcome().risk })));
  expect(await screen.findByText("Applied")).toBeInTheDocument();
});

test("Apply with no current outcome still calls onOutcome so the case is refetched", async () => {
  const { onOutcome } = setup(withMessages(message({ proposals: [proposal()] })),
    { decide: vi.fn(async () => ({ proposal: proposal({ status: "failed", error: "Recalc failed" }), current: null })) });
  await userEvent.click(await screen.findByRole("button", { name: "Apply" }));
  await waitFor(() => expect(onOutcome).toHaveBeenCalledWith(null));
  expect(await screen.findByText("Failed: Recalc failed")).toBeInTheDocument();
});

test("Ignore does not call onOutcome", async () => {
  const { client, onOutcome } = setup(withMessages(message({ proposals: [proposal()] })),
    { decide: vi.fn(async () => ({ proposal: proposal({ status: "ignored" }), current: null })) });
  await userEvent.click(await screen.findByRole("button", { name: "Ignore" }));
  expect(await screen.findByText("Ignored")).toBeInTheDocument();
  expect(client.decide).toHaveBeenCalledWith("c1", "p1", "ignore");
  expect(onOutcome).not.toHaveBeenCalled();
});

test("a stale proposal says so", async () => {
  setup(withMessages(message({ proposals: [proposal({ status: "stale" })] })));
  expect(await screen.findByText("Changed since — ask again")).toBeInTheDocument();
});

test("New chat starts an empty thread and previous chats are listed", async () => {
  const state = { ...withMessages(message()), previous: [{ id: "t0", summary: "Earlier we checked the bill.", created_at: "2026-10-15T10:00:00Z" }] };
  const { client } = setup(state);
  expect(await screen.findByText("Earlier we checked the bill.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "New chat" }));
  await waitFor(() => expect(screen.queryByText("The total is Rs 48,500.")).toBeNull());
  expect(client.newChat).toHaveBeenCalledWith("c1");
});

test("a 429 shows the limit text and keeps the typed text", async () => {
  setup(empty, { ask: vi.fn(async () => { throw new ApiError(429, "Daily limit of 200 chat messages reached"); }) });
  await userEvent.type(await screen.findByRole("textbox"), "one more");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Daily limit of 200 chat messages reached")).toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("one more");
});

test("Enter sends, but not while an IME is composing", async () => {
  const { client } = setup();
  const box = await screen.findByRole("textbox");
  await userEvent.type(box, "hello");
  fireEvent.keyDown(box, { key: "Enter", isComposing: true });
  expect(client.ask).not.toHaveBeenCalled();
  fireEvent.keyDown(box, { key: "Enter" });
  await waitFor(() => expect(client.ask).toHaveBeenCalledTimes(1));
});

test("a 409 on Apply refetches the thread so the card shows its real status, with a notice", async () => {
  const getChat = vi.fn()
    .mockResolvedValueOnce(withMessages(message({ proposals: [proposal()] })))
    .mockResolvedValue(withMessages(message({ proposals: [proposal({ status: "applied" })] })));
  const { onOutcome } = setup(empty, { getChat, decide: vi.fn(async () => { throw new ApiError(409, "Not pending"); }) });
  await userEvent.click(await screen.findByRole("button", { name: "Apply" }));
  expect(await screen.findByText("Applied")).toBeInTheDocument();
  expect(screen.getByText("Already decided")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
  expect(onOutcome).not.toHaveBeenCalled();
});

test("when chat is turned off the panel is not shown and the caller is told", async () => {
  const onUnavailable = vi.fn();
  const { client } = setup(empty, { getChat: vi.fn(async () => { throw new ApiError(404, "Not found"); }) }, { onUnavailable });
  await waitFor(() => expect(client.getChat).toHaveBeenCalled());
  await waitFor(() => expect(onUnavailable).toHaveBeenCalled());
  expect(screen.queryByRole("textbox")).toBeNull();
});
