"""Forgeries of one field on a phone photo of a bill: retyped, a copied digit, or edited by an image model
(the AIForge-Doc method: crop with context, mark the field, edit, then paste back only the field)."""

import hashlib
import io
import logging
import time
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)
GREEN = (0, 220, 60)
ATTEMPTS = 6  # waits of 10, 20, 40, 80, 160 s between them


class ImageEditor(Protocol):
    def edit(self, png: bytes, prompt: str) -> bytes | None: ...


def _decode(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).copy()


def _jpeg(arr: np.ndarray, quality: int) -> bytes:
    out = io.BytesIO()
    Image.fromarray(arr).save(out, "JPEG", quality=int(quality))
    return out.getvalue()


def _box(box) -> tuple[int, int, int, int]:
    return int(box[0]), int(box[1]), int(np.ceil(box[2])), int(np.ceil(box[3]))


def edit_is_local(before: bytes, after: bytes, box, pad: int = 8) -> bool:
    """Only the field changed: outside the (padded) box, pixels differ no more than a JPEG re-save does."""
    a, b = _decode(before).astype(np.int16), _decode(after).astype(np.int16)
    if a.shape != b.shape:
        return False
    diff = np.abs(a - b).max(axis=2)
    x0, y0, x1, y1 = _box(box)
    diff[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = 0
    # a re-save shifts pixels a little everywhere; a stray edit changes a few pixels a lot
    return float(np.percentile(diff, 99)) < 12 and int((diff > 40).sum()) <= 50


def paste_retype(jpg: bytes, box, value: str, quality: int) -> bytes | None:
    """Cover the field with the paper colour and type the new value in a similar size."""
    img = _decode(jpg)
    x0, y0, x1, y1 = _box(box)
    ring = np.concatenate([img[max(0, y0 - 6):y0, x0:x1].reshape(-1, 3), img[y1:y1 + 6, x0:x1].reshape(-1, 3)])
    paper = tuple(int(v) for v in np.median(ring, axis=0))
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    d.rectangle((x0, y0, x1, y1), fill=paper)
    d.text((x0, y0 - 2), value, fill=(40, 40, 48), font=ImageFont.load_default(size=max(10, int((y1 - y0) * 1.2))))
    out = _jpeg(np.asarray(pil), quality)
    return out if edit_is_local(jpg, out, box) else None


def copy_move_digit(jpg: bytes, box, quality: int, seed: int) -> bytes | None:
    """Copy the field's last digit over one of its earlier digits (a 3 becomes the 8 from the same number)."""
    img = _decode(jpg)
    x0, y0, x1, y1 = _box(box)
    width = max(6, int((y1 - y0) * 0.55))
    if x1 - x0 < 3 * width:
        return None
    rng = np.random.default_rng(seed)
    src = img[y0:y1, x1 - width:x1].copy()
    tx = int(rng.integers(x0 + width * 3 // 2, x1 - 2 * width)) if x1 - 2 * width > x0 + width * 3 // 2 else x0 + width
    img[y0:y1, tx:tx + width] = src
    out = _jpeg(img, quality)
    return out if edit_is_local(jpg, out, box) else None


def gemini_edit(editor: ImageEditor, jpg: bytes, box, value: str, quality: int, cache_dir: Path,
                paste_back: bool = True) -> bytes | None:
    """The image model edits a context crop; only the field box goes back into the photo."""
    img = _decode(jpg)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = _box(box)
    mx, my = max(150, (x1 - x0) // 2), max(150, (y1 - y0) // 2)
    cx0, cy0, cx1, cy1 = max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)
    crop = Image.fromarray(img[cy0:cy1, cx0:cx1])
    ImageDraw.Draw(crop).rectangle((x0 - cx0 - 3, y0 - cy0 - 3, x1 - cx0 + 3, y1 - cy0 + 3), outline=GREEN, width=3)
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    prompt = (f"Change only the number inside the green box to {value}. Match the font, size, ink colour, "
              "blur and paper texture exactly. Remove the green box. Change nothing else.")
    key = hashlib.sha256(buf.getvalue() + prompt.encode()).hexdigest()
    cached = Path(cache_dir) / f"{key}.png"
    if cached.is_file():
        result = cached.read_bytes()
    else:
        result = editor.edit(buf.getvalue(), prompt)
        if result is None:
            log.warning("image model returned nothing for %s", key[:12])
            return None
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        cached.write_bytes(result)
    edited = np.asarray(Image.open(io.BytesIO(result)).convert("RGB").resize((cx1 - cx0, cy1 - cy0), Image.LANCZOS))
    out_img = img.copy()
    if paste_back:
        out_img[y0:y1, x0:x1] = edited[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0]
    else:
        out_img[cy0:cy1, cx0:cx1] = edited
    out = _jpeg(out_img, quality)
    if not edit_is_local(jpg, out, box):
        log.warning("image model edit was not local for %s: discarded", key[:12])
        return None
    return out


class GeminiImageEditor:
    """Gemini image editing on Vertex AI (location global)."""

    def __init__(self, project: str, model: str = "gemini-3.1-flash-image"):
        from google import genai

        self.client = genai.Client(vertexai=True, project=project, location="global")
        self.model = model

    def edit(self, png: bytes, prompt: str) -> bytes | None:
        from google.genai import types

        from google.genai import errors

        response = None
        for attempt in range(ATTEMPTS):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=[prompt, types.Part.from_bytes(data=png, mime_type="image/png")],
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
                break
            except (errors.ClientError, errors.ServerError) as e:
                # 429 (quota) and 5xx are worth waiting for; anything else (a refusal, a bad request) is not
                if getattr(e, "code", None) != 429 and not isinstance(e, errors.ServerError):
                    log.warning("image model refused: %s", e)
                    return None
                wait = 10 * 2 ** attempt
                log.info("image model busy (%s), retry in %ss", getattr(e, "code", "?"), wait)
                time.sleep(wait)
            except Exception:
                log.warning("image model call failed", exc_info=True)
                return None
        if response is None:
            log.warning("image model still busy after %d attempts", ATTEMPTS)
            return None
        for part in (response.candidates or [None])[0].content.parts if response.candidates else []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return part.inline_data.data
        return None
