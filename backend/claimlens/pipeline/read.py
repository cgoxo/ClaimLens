"""Step 2 (Read): turn each document into pages, spans, drawings, file info and page images."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import pymupdf

from claimlens.models import FileInfo, PageInfo, Span
from claimlens.ocr import Ocr
from claimlens.storage import Storage

DPI = 110
IMAGE_TYPES = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}
OCR_LAYER_FONTS = ("glyphless",)
COLUMN_GAP = re.compile(r" {2,}")


@dataclass
class Drawing:
    doc: str
    page: int
    rect: tuple[float, float, float, float]
    fill: tuple[float, ...] | None
    seqno: int


@dataclass
class ReadResult:
    pages: list[PageInfo] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    hidden_layer: list[Span] = field(default_factory=list)
    drawings: list[Drawing] = field(default_factory=list)
    files: list[FileInfo] = field(default_factory=list)

    def extend(self, other: "ReadResult") -> None:
        self.pages += other.pages
        self.spans += other.spans
        self.hidden_layer += other.hidden_layer
        self.drawings += other.drawings
        self.files += other.files


def open_document(data: bytes, filename: str) -> pymupdf.Document:
    """Open a PDF, or wrap an uploaded photo as a one-page PDF."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in IMAGE_TYPES:
        img = pymupdf.open(stream=data, filetype=IMAGE_TYPES[ext])
        return pymupdf.open("pdf", img.convert_to_pdf())
    return pymupdf.open(stream=data, filetype="pdf")


def _chunks(trace: dict, doc: str, page: int) -> list[Span]:
    """Split one texttrace run at column gaps (2+ spaces) into spans with their own boxes."""
    chars = trace["chars"]
    text = "".join(chr(c[0]) for c in chars)
    spans, start = [], 0
    for gap in [*COLUMN_GAP.finditer(text), None]:
        end = gap.start() if gap else len(text)
        piece = chars[start:end]
        if text[start:end].strip():
            boxes = [c[3] for c in piece]
            spans.append(Span(
                doc=doc, page=page, text=text[start:end].strip(), font=trace["font"],
                size=round(trace["size"], 2), seqno=trace["seqno"],
                bbox=(min(b[0] for b in boxes), min(b[1] for b in boxes),
                      max(b[2] for b in boxes), max(b[3] for b in boxes)),
            ))
        start = gap.end() if gap else end
    return spans


def _covers_page(page: pymupdf.Page) -> bool:
    area = page.rect.width * page.rect.height
    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & page.rect
        if r.width * r.height >= 0.9 * area:
            return True
    return False


def read_document(doc: str, data: bytes, filename: str, case_id: str,
                  storage: Storage, ocr: Ocr,
                  on_page: Callable[[str, int, str], None] | None = None, start_page: int = 1,
                  card_id: str | None = None, key: str = "", file_index: int = 0) -> ReadResult:
    """Read one uploaded file into its stream (`doc`), numbering its pages from `start_page`."""
    pdf = open_document(data, filename)
    is_photo = filename.rsplit(".", 1)[-1].lower() in IMAGE_TYPES
    meta = pdf.metadata or {}
    result = ReadResult(files=[FileInfo(
        doc=doc, card_id=card_id, key=key, first_page=start_page, producer=meta.get("producer") or "", creator=meta.get("creator") or "",
        created=meta.get("creationDate") or "", modified=meta.get("modDate") or "",
        eof_count=max(1, data.count(b"%%EOF")) if not is_photo else 1,
    )])

    for file_page, page in enumerate(pdf, start=1):
        index = start_page + file_page - 1  # page number in the stream
        visible, invisible = [], []
        for trace in page.get_texttrace():
            target = invisible if trace["type"] == 3 or trace["font"].lower().startswith(OCR_LAYER_FONTS) else visible
            target += _chunks(trace, doc, index)

        full_image = _covers_page(page)
        if is_photo:
            kind = "image"
        elif full_image and invisible:
            kind = "scanned_with_text"
        elif full_image and not visible:
            kind = "scanned"
        else:
            kind = "digital"

        pix = page.get_pixmap(dpi=DPI)
        png = pix.tobytes("png")
        png_key = f"cases/{case_id}/pages/{doc}/{index}.png"
        storage.put(png_key, png, "image/png")

        if kind == "digital":
            spans = visible
            text = page.get_text()
        else:
            spans = ocr.read_page(png, doc, index, page.rect.width, page.rect.height)
            text = " ".join(s.text for s in spans)
            if not spans:
                kind = "unreadable"
            result.hidden_layer += invisible

        result.spans += spans
        result.pages.append(PageInfo(doc=doc, page=index, kind=kind, text=text,
                                     width=page.rect.width, height=page.rect.height, png_key=png_key,
                                     card_id=card_id, file_index=file_index, file_page=file_page,
                                     dhash=dhash_of(pix)))
        for d in page.get_drawings():
            if d.get("fill") is not None and d.get("rect") is not None:
                result.drawings.append(Drawing(doc=doc, page=index, rect=tuple(d["rect"]),
                                               fill=tuple(d["fill"]), seqno=d.get("seqno", 0)))
        if on_page:
            on_page(doc, file_page, kind)
    return result


def dhash_of(pix: pymupdf.Pixmap) -> str:
    """64-bit difference hash: shrink to 9x8 grey and compare each cell with its right neighbour.

    Two photos or scans of the same page land within a few bits of each other.
    """
    grey = pymupdf.Pixmap(pymupdf.csGRAY, pix) if pix.n > 1 else pix
    w, h, samples, stride = grey.width, grey.height, grey.samples, grey.stride

    def cell(cx: int, cy: int) -> float:
        x0, x1 = cx * w // 9, max(cx * w // 9 + 1, (cx + 1) * w // 9)
        y0, y1 = cy * h // 8, max(cy * h // 8 + 1, (cy + 1) * h // 8)
        step_x, step_y = max(1, (x1 - x0) // 8), max(1, (y1 - y0) // 8)  # sample, don't sum every pixel
        values = [samples[y * stride + x] for y in range(y0, y1, step_y) for x in range(x0, x1, step_x)]
        return sum(values) / len(values)

    bits = 0
    for cy in range(8):
        row = [cell(cx, cy) for cx in range(9)]
        for cx in range(8):
            bits = bits << 1 | (row[cx] > row[cx + 1])
    return f"{bits:016x}"


def _overlap(a: tuple, b: tuple) -> float:
    """Share of rect a covered by rect b."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    area = (a[2] - a[0]) * (a[3] - a[1])
    return max(0, w) * max(0, h) / area if area > 0 else 0


def covered_spans(read: ReadResult) -> list[tuple[Span, Drawing]]:
    """Text painted over by a near-white box drawn after it: invisible to a person, present in the file."""
    out = []
    for d in read.drawings:
        if not d.fill or min(d.fill) < 0.95:
            continue
        out += [(s, d) for s in read.spans
                if s.doc == d.doc and s.page == d.page and s.seqno < d.seqno and _overlap(s.bbox, d.rect) >= 0.5]
    return out


def reading_lines(spans: list[Span]) -> list[list[Span]]:
    """Spans grouped into visual lines (top to bottom), each line left to right."""
    lines: list[list[Span]] = []
    for s in sorted(spans, key=lambda s: (s.bbox[1], s.bbox[0])):
        mid = (s.bbox[1] + s.bbox[3]) / 2
        if lines and abs(mid - (lines[-1][0].bbox[1] + lines[-1][0].bbox[3]) / 2) < 3:
            lines[-1].append(s)
        else:
            lines.append([s])
    return [sorted(line, key=lambda s: s.bbox[0]) for line in lines]


def visible_text(read: ReadResult, doc: str, page: int) -> str:
    """The page as a person sees it: digital pages rebuilt from spans, minus covered text."""
    info = next((p for p in read.pages if p.doc == doc and p.page == page), None)
    if info is None or info.kind != "digital":
        return info.text if info else ""
    hidden = {id(s) for s, _ in covered_spans(read)}
    spans = [s for s in read.spans if s.doc == doc and s.page == page and id(s) not in hidden]
    return "\n".join("   ".join(s.text for s in line) for line in reading_lines(spans))
