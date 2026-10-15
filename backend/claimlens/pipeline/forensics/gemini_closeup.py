"""Gemini close-up: show the model each number at full resolution, with a little context, and ask whether
it looks different from the print around it. Measured before use: vision models were at chance on this task
in AIForge-Doc, so it ships only if it beats the keep rule."""

import hashlib
import json
import logging
from pathlib import Path

import cv2
import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo
from claimlens.pipeline.forensics.words import clip_box, is_number

log = logging.getLogger(__name__)
MAX_NUMBERS = 30
MAX_SIDE = 512
PROMPT = ("This is a close-up of one number on a photographed bill, with the print around it. Does the number "
          "look edited compared with its surroundings (different font, sharpness, ink, background, alignment or "
          "grain)? Answer only JSON: {\"looks_edited\": true|false, \"confidence\": 0..1, \"why\": \"...\"}")


class GeminiVision:
    def __init__(self, project: str, model: str = "gemini-2.5-flash", location: str = "global"):
        from google import genai

        self.client = genai.Client(vertexai=True, project=project, location=location)
        self.model = model

    def ask(self, png: bytes, prompt: str) -> str | None:
        from google.genai import types

        try:
            response = self.client.models.generate_content(
                model=self.model, contents=[prompt, types.Part.from_bytes(data=png, mime_type="image/png")],
                config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"))
            return response.text
        except Exception:
            log.warning("close-up call failed", exc_info=True)
            return None


def _score(answer: str | None) -> float:
    """1 = surely edited, 0 = surely genuine, 0.5 = no usable answer."""
    try:
        data = json.loads(answer or "")
        confidence = float(np.clip(float(data["confidence"]), 0, 1))
        return 0.5 + confidence / 2 if bool(data["looks_edited"]) else 0.5 - confidence / 2
    except (ValueError, TypeError, KeyError):
        return 0.5


class GeminiCloseup:
    name = "gemini_closeup"

    def __init__(self, vision, cache_dir: Path | None = None):
        self.vision, self.cache_dir = vision, Path(cache_dir) if cache_dir else None

    def applies(self, info: ImageInfo) -> bool:
        return True

    def _ask(self, png: bytes) -> str | None:
        key = hashlib.sha256(png + PROMPT.encode()).hexdigest()
        cached = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if cached and cached.is_file():
            return cached.read_text()
        answer = self.vision.ask(png, PROMPT)
        if cached and answer is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(answer)
        return answer

    def heatmap(self, img: np.ndarray, info: ImageInfo, words) -> np.ndarray | None:
        numbers = [(b, t) for b, t in words if is_number(t)][:MAX_NUMBERS]
        if not numbers:
            return None
        heat, any_answer = np.zeros(img.shape[:2], np.float32), False
        h, w = img.shape[:2]
        for box, _ in numbers:
            b = clip_box(box, img.shape)
            if b is None:
                continue
            x0, y0, x1, y1 = b
            mx, my = (x1 - x0), (y1 - y0) * 2
            crop = img[max(0, y0 - my):min(h, y1 + my), max(0, x0 - mx):min(w, x1 + mx)]
            scale = min(1.0, MAX_SIDE / max(crop.shape[:2]))
            if scale < 1:
                crop = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)), cv2.INTER_AREA)
            ok, png = cv2.imencode(".png", cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
            score = _score(self._ask(png.tobytes())) if ok else 0.5
            any_answer = any_answer or score != 0.5
            heat[y0:y1, x0:x1] = np.maximum(heat[y0:y1, x0:x1], score)
        return heat if any_answer else None
