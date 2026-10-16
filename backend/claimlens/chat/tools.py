"""The tools the chat model may call: all read-only. Results are JSON text (plus an image for view_region)."""
import io
import json
import logging
import math
from dataclasses import dataclass

from PIL import Image

from claimlens.models import Case, Finding, PageInfo
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.forensics.base import field_score, safe_heatmap
from claimlens.pipeline.forensics.chars import CHARS
from claimlens.pipeline.forensics.ela import ELA
from claimlens.pipeline.forensics.image import load_image
from claimlens.pipeline.read import DPI

log = logging.getLogger(__name__)

MAX_HITS = 10
HIT_CONTEXT = 40  # characters either side of a hit
MARGIN = 0.04
MAX_SIDE = 1600
PHOTO_KINDS = ("image", "scanned", "scanned_with_text")


@dataclass
class ToolResult:
    text: str
    image: bytes | None = None


_DOC = {"type": "string", "description": "Document stream: 'claim' or 'policy'."}
_PAGE = {"type": "integer", "description": "Page number within that stream, starting at 1."}
_BBOX = {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
         "description": "[x0, y0, x1, y1] in page points."}
_CITATION = {
    "type": "object",
    "properties": {"doc": _DOC, "page": _PAGE,
                   "quote": {"type": "string", "description": "Exact words copied from that page."},
                   "bbox": _BBOX},
    "required": ["doc", "page", "quote"],
}
_PROPOSAL = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["review_finding", "set_severity", "add_finding", "correct_fact"]},
        "reason": {"type": "string"},
        "finding_id": {"type": "string"},
        "action": {"type": "string", "enum": ["accept", "dismiss", "restore"]},
        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "coverage"]},
        "title": {"type": "string"},
        "detail": {"type": "string"},
        "citations": {"type": "array", "items": _CITATION},
        "path": {"type": "string"},
        "value": {"type": "string"},
        "evidence": {"type": "object",
                     "properties": {"doc": _DOC, "page": _PAGE, "bbox": _BBOX},
                     "required": ["doc", "page", "bbox"]},
    },
    "required": ["type"],
}


def _fn(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}


TOOLS: list[dict] = [
    _fn("search_text", "Search the text of every page, ignoring case. Returns up to 10 hits with the words around each.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("get_page", "The full text of one page.", {"doc": _DOC, "page": _PAGE}, ["doc", "page"]),
    _fn("list_findings", "All findings of the case: id, code, severity, title, status and first citation."),
    _fn("get_finding", "One finding in full, with its history of versions.",
        {"finding_id": {"type": "string"}}, ["finding_id"]),
    _fn("get_facts", "The claim and policy facts read from the documents."),
    _fn("get_settlement", "How the payable amount was worked out, line by line."),
    _fn("view_region", "Look at a page, or part of it, as an image.",
        {"doc": _DOC, "page": _PAGE, "bbox": _BBOX}, ["doc", "page"]),
    _fn("check_region", "Pixel checks (error level analysis and character consistency) for whether an area of a "
        "photographed or scanned page looks edited. A signal, not proof.",
        {"doc": _DOC, "page": _PAGE, "bbox": _BBOX}, ["doc", "page", "bbox"]),
    _fn("final_answer", "Give the answer to the reviewer. Call this once, when done.",
        {"answer": {"type": "string"},
         "citations": {"type": "array", "items": _CITATION},
         "proposals": {"type": "array", "items": _PROPOSAL}},
        ["answer", "citations", "proposals"]),
]


def _json(obj) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def _error(msg: str) -> ToolResult:
    return ToolResult(_json({"error": msg}))


def _cut(text: str, limit: int) -> str:
    suffix = " [truncated]"
    return text if len(text) <= limit else text[:max(0, limit - len(suffix))] + suffix


def _page(ctx: Ctx, doc, page) -> PageInfo:
    p = next((p for p in ctx.read.pages if p.doc == doc and p.page == page), None)
    if p is None:
        raise ValueError("no such page")
    return p


def _bbox(raw) -> tuple[float, float, float, float]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("bbox must be [x0, y0, x1, y1]")
    x0, y0, x1, y1 = (float(v) for v in raw)
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        raise ValueError("bbox values must be finite numbers")
    if not x1 > x0 or not y1 > y0:
        raise ValueError("bbox has no area")
    return x0, y0, x1, y1


def _search_text(args, deps, case, ctx) -> dict:
    query = str(args["query"]).strip().lower()
    if not query:
        raise ValueError("query is empty")
    hits = []
    for p in ctx.read.pages:
        low = p.text.lower()
        at = low.find(query)
        while at != -1 and len(hits) < MAX_HITS:
            start, end = max(0, at - HIT_CONTEXT), at + len(query) + HIT_CONTEXT
            hits.append({"doc": p.doc, "page": p.page, "snippet": p.text[start:end]})
            at = low.find(query, at + len(query))
        if len(hits) >= MAX_HITS:
            break
    return {"hits": hits}


def _get_page(args, deps, case, ctx) -> dict:
    p = _page(ctx, args["doc"], int(args["page"]))
    return {"doc": p.doc, "page": p.page, "kind": p.kind, "text": p.text}


def _status(f: Finding) -> str:
    action = f.review.action if f.review else None
    return "dismissed" if action == "dismiss" else "accepted" if action == "accept" else "active"


def _list_findings(args, deps, case, ctx) -> dict:
    out = []
    for f in deps.db.get_findings(case.id):
        if f.removed:
            continue
        out.append({"id": f.id, "code": f.code, "severity": f.severity, "title": f.title, "status": _status(f),
                    "citation": f.citations[0].model_dump(mode="json") if f.citations else None})
    return {"findings": out}


def _get_finding(args, deps, case, ctx) -> dict:
    fid = str(args["finding_id"])
    f = next((f for f in deps.db.get_findings(case.id) if f.id == fid), None)
    if f is None:
        raise ValueError("no such finding")
    if f.removed:
        raise ValueError("that finding was removed by a correction")
    return {"finding": f.model_dump(mode="json"), "status": _status(f),
            "versions": deps.db.get_finding_versions(case.id, fid)}


def _get_facts(args, deps, case, ctx) -> dict:
    context = case.context or {}
    return {"claim": context.get("claim"), "policy": context.get("policy")}


def _get_settlement(args, deps, case, ctx) -> dict:
    outcome = case.current if case.current and case.current.settlement else case.analysis
    if outcome is None or outcome.settlement is None:
        raise ValueError("no settlement for this case")
    return outcome.settlement.model_dump(mode="json")


def _view_region(args, deps, case, ctx) -> ToolResult:
    p = _page(ctx, args["doc"], int(args["page"]))
    box = _bbox(args["bbox"]) if args.get("bbox") else None
    img = Image.open(io.BytesIO(deps.storage.get(p.png_key))).convert("RGB")
    if box:
        k = DPI / 72
        mx, my = (box[2] - box[0]) * MARGIN, (box[3] - box[1]) * MARGIN
        left, top = max(0, int((box[0] - mx) * k)), max(0, int((box[1] - my) * k))
        right, bottom = min(img.width, int((box[2] + mx) * k) + 1), min(img.height, int((box[3] + my) * k) + 1)
        if right <= left or bottom <= top:
            raise ValueError("bbox is outside the page")
        img = img.crop((left, top, right, bottom))
    if max(img.size) > MAX_SIDE:
        f = MAX_SIDE / max(img.size)
        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG")
    return ToolResult(_json({"doc": p.doc, "page": p.page, "width": img.width, "height": img.height}), out.getvalue())


def _original_key(ctx: Ctx, p: PageInfo) -> str | None:
    files = [f for f in ctx.read.files if f.doc == p.doc and f.first_page <= p.page]
    return max(files, key=lambda f: f.first_page).key if files else None


def _check_region(args, deps, case, ctx) -> dict:
    p = _page(ctx, args["doc"], int(args["page"]))
    if p.kind not in PHOTO_KINDS:
        return {"error": "only for photo or scanned pages"}
    box = _bbox(args["bbox"])
    overlap = (max(box[0], 0), max(box[1], 0), min(box[2], p.width), min(box[3], p.height))
    if overlap[2] <= overlap[0] or overlap[3] <= overlap[1] or \
            (overlap[2] - overlap[0]) * (overlap[3] - overlap[1]) < 0.5 * (box[2] - box[0]) * (box[3] - box[1]):
        raise ValueError("bbox is outside the page")
    key = _original_key(ctx, p) if p.kind == "image" else None
    img, info = load_image(deps.storage.get(key or p.png_key))
    if img is None:
        raise ValueError("the image could not be loaded")
    # the detectors compare each word with the page's other words, so run them on the whole page, then score the box
    sx, sy = info.size[0] / p.width, info.size[1] / p.height  # page points -> analysed pixels
    words = [((s.bbox[0] * sx, s.bbox[1] * sy, s.bbox[2] * sx, s.bbox[3] * sy), s.text)
             for s in ctx.spans_on(p.doc, p.page)]
    pixels = (box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy)
    scores = {}
    for name, detector in (("ela", ELA), ("chars", CHARS)):
        heat = safe_heatmap(detector, img, info, words)
        scores[name] = None if heat is None else round(field_score(heat, pixels), 3)
    return {**scores, "note": "signal, not proof"}


_HANDLERS = {"search_text": _search_text, "get_page": _get_page, "list_findings": _list_findings,
             "get_finding": _get_finding, "get_facts": _get_facts, "get_settlement": _get_settlement,
             "view_region": _view_region, "check_region": _check_region}


def run_tool(name: str, args: dict, deps, case: Case, ctx: Ctx) -> ToolResult:
    """Run one tool. An unknown tool or bad arguments is an error result, never an exception."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return _error(f"unknown tool: {name}")
    try:
        result = handler(args or {}, deps, case, ctx)
    except ValueError as e:
        return _error(str(e))
    except (KeyError, TypeError) as e:
        return _error(f"bad arguments: {e!r}")
    except Exception:
        log.warning("tool %s failed", name, exc_info=True)
        return _error("the tool failed")
    image = None
    if isinstance(result, ToolResult):
        result, image = result.text, result.image
    text = result if isinstance(result, str) else _json(result)
    return ToolResult(_cut(text, deps.settings.chat_tool_chars), image)
