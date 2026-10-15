"""The detector contract: a heatmap in [0, 1] the size of the image, or None for "no opinion" (never "clean")."""

import logging
from typing import Protocol

import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo

log = logging.getLogger(__name__)
MIN_SIDE = 600  # smaller than this, there's too little detail to judge
Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in analysed-image pixels
Word = tuple[Box, str]  # an OCR word: where it is and what it says


class Detector(Protocol):
    name: str

    def applies(self, info: ImageInfo) -> bool: ...
    def heatmap(self, img: np.ndarray, info: ImageInfo, words: list[Word]) -> np.ndarray | None: ...


def safe_heatmap(detector: Detector, img: np.ndarray, info: ImageInfo, words: list[Word]) -> np.ndarray | None:
    """Run one detector; anything that stops it from judging this image is "no opinion", never a crash."""
    if max(info.size) < MIN_SIDE:
        return None
    try:
        if not detector.applies(info):
            return None
        heat = detector.heatmap(img, info, words)
    except Exception:
        log.warning("detector %s failed", detector.name, exc_info=True)
        return None
    if heat is None or heat.shape != img.shape[:2]:
        return None
    return np.clip(heat.astype(np.float32), 0, 1)


def field_score(heat: np.ndarray, box: Box, pad: int = 4) -> float:
    """How edited the area of one field looks: the 95th percentile of the heatmap inside the (padded) box."""
    h, w = heat.shape
    x0, y0 = max(0, int(box[0]) - pad), max(0, int(box[1]) - pad)
    x1, y1 = min(w, int(np.ceil(box[2])) + pad), min(h, int(np.ceil(box[3])) + pad)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(np.percentile(heat[y0:y1, x0:x1], 95))
