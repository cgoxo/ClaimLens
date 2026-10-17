import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Client } from "../api/client";
import type { CaseCard, PageMeta } from "../api/types";
import PageViewer from "./PageViewer";

const page = (n: number, card_id: string | null, file_index = 0, doc = "claim"): PageMeta =>
  ({ doc, page: n, kind: "digital", width: 600, height: 800, card_id, file_index });
const client = { pageImageUrl: vi.fn(async () => "blob:x") } as unknown as Client;
const claim: CaseCard = { id: "claim", role: "claim", label: "Claim",
  files: [{ name: "claim-form.pdf", pages: 1 }, { name: "hospital-bill-1.jpg", pages: 1 }, { name: "hospital-bill-2.jpg", pages: 1 }] };

function show(pages: PageMeta[], cards: CaseCard[]) {
  render(<PageViewer caseId="c1" pages={pages} cards={cards} client={client} selected={null}
    selectedNumber={null} selectedDetail="" />);
}

test("claim pages are grouped under the file they came from", () => {
  show([page(1, "claim", 0), page(2, "claim", 1), page(3, "claim", 2), page(4, "claim", 2)], [claim]);
  const group = screen.getByRole("group", { name: "hospital-bill-2.jpg" });
  expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["3", "4"]);
  expect(screen.getByRole("group", { name: "claim-form.pdf" })).toBeInTheDocument();
});

test("a case from before cards shows one group per document", () => {
  show([page(1, null), page(2, null)], []);
  expect(within(screen.getByRole("group", { name: "Claim" })).getAllByRole("button")).toHaveLength(2);
});

describe("ask about an area", () => {
  // jsdom has no PointerEvent, so fireEvent would drop clientX and clientY
  beforeAll(() => {
    if (!("PointerEvent" in window)) {
      class PointerEventShim extends MouseEvent {
        pointerId: number;
        constructor(type: string, init: MouseEventInit & { pointerId?: number } = {}) {
          super(type, init);
          this.pointerId = init.pointerId ?? 1;
        }
      }
      vi.stubGlobal("PointerEvent", PointerEventShim);
    }
  });
  afterAll(() => vi.unstubAllGlobals());

  const rect = { left: 100, top: 50, width: 300, height: 400, right: 400, bottom: 450, x: 100, y: 50, toJSON() {} };

  async function open(onSelectArea = vi.fn()) {
    render(<PageViewer caseId="c1" pages={[page(1, null)]} cards={[]} client={client} selected={null}
      selectedNumber={null} selectedDetail="" onSelectArea={onSelectArea} />);
    const img = await screen.findByAltText("claim page 1");
    img.getBoundingClientRect = () => rect as DOMRect;
    await userEvent.click(screen.getByRole("button", { name: "Ask about an area" }));
    return { layer: screen.getByTestId("select-layer"), onSelectArea };
  }

  test("a drag becomes a box in page points", async () => {
    const { layer, onSelectArea } = await open();
    // the image is 300x400 px for a 600x800 pt page: 2 points per pixel
    fireEvent.pointerDown(layer, { clientX: 130, clientY: 90, pointerId: 1 });
    fireEvent.pointerMove(layer, { clientX: 250, clientY: 200, pointerId: 1 });
    expect(screen.getByTestId("drag-box")).toBeInTheDocument();
    fireEvent.pointerUp(layer, { clientX: 250, clientY: 200, pointerId: 1 });
    expect(onSelectArea).toHaveBeenCalledWith({ doc: "claim", page: 1, bbox: [60, 80, 300, 300] });
  });

  test("dragging up-left still gives x0 < x1 and y0 < y1", async () => {
    const { layer, onSelectArea } = await open();
    fireEvent.pointerDown(layer, { clientX: 250, clientY: 200, pointerId: 1 });
    fireEvent.pointerUp(layer, { clientX: 130, clientY: 90, pointerId: 1 });
    expect(onSelectArea).toHaveBeenCalledWith({ doc: "claim", page: 1, bbox: [60, 80, 300, 300] });
  });

  test("a tiny drag is ignored", async () => {
    const { layer, onSelectArea } = await open();
    fireEvent.pointerDown(layer, { clientX: 130, clientY: 90, pointerId: 1 });
    fireEvent.pointerUp(layer, { clientX: 134, clientY: 140, pointerId: 1 });
    expect(onSelectArea).not.toHaveBeenCalled();
  });

  test("Escape leaves selection mode", async () => {
    await open();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByTestId("select-layer")).toBeNull();
  });

  test("without onSelectArea there is no toggle", () => {
    show([page(1, null)], []);
    expect(screen.queryByRole("button", { name: "Ask about an area" })).toBeNull();
  });
});
