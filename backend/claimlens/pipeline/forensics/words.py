"""Word-level comparison: on documents every word has sharp text edges, so raw maps light up on all text.
Measuring a signal inside each word box and comparing words with each other cancels that out."""

import math

import numpy as np

MIN_WORDS = 5


def clip_box(box, shape) -> tuple[int, int, int, int] | None:
    h, w = shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    return (x0, y0, x1, y1) if x1 - x0 >= 4 and y1 - y0 >= 4 else None


def odd_one_out(values: list[float | None], spread: float) -> list[float | None]:
    """How far each value is from the page's typical word, either way: |log(v / median)| / log(spread), in [0, 1]."""
    present = [v for v in values if v is not None and v > 0]
    if len(present) < MIN_WORDS:
        return [None] * len(values)
    typical = float(np.median(present))
    return [None if v is None or v <= 0 else min(1.0, abs(math.log(v / typical)) / math.log(spread))
            for v in values]


def paint(shape, boxes: list, scores: list[float | None]) -> np.ndarray | None:
    if all(s is None for s in scores):
        return None
    heat = np.zeros(shape[:2], np.float32)
    for box, score in zip(boxes, scores):
        if box is not None and score is not None:
            x0, y0, x1, y1 = box
            heat[y0:y1, x0:x1] = np.maximum(heat[y0:y1, x0:x1], score)
    return heat
