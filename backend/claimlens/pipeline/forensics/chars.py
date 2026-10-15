"""Character consistency: compare each number with the other text on the page.

An edited number usually differs from its neighbours in ink colour, the paper behind it, or sharpness.
Pages legitimately mix styles (a bold TOTAL), so colours are compared with every word, and sharpness only
with words of the same style (height and stroke width)."""

import re

import cv2
import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo

NUMBER = re.compile(r"\d[\d,./-]*\d|\d")
MIN_GROUP = 5


def _features(img: np.ndarray, lab: np.ndarray, grey: np.ndarray, box) -> np.ndarray | None:
    h, w = grey.shape
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = grey[y0:y1, x0:x1]
    _, ink = cv2.threshold(crop, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if ink.sum() < 8:
        return None
    sharp = float(np.log1p(cv2.Laplacian(crop, cv2.CV_32F).var()))
    stroke = float(2 * np.median(cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)[ink > 0]))
    ink_lab = np.median(lab[y0:y1, x0:x1][ink > 0], axis=0)
    ring = np.ones((min(h, y1 + 3) - max(0, y0 - 3), min(w, x1 + 3) - max(0, x0 - 3)), bool)
    ring[y0 - max(0, y0 - 3):y0 - max(0, y0 - 3) + (y1 - y0), x0 - max(0, x0 - 3):x0 - max(0, x0 - 3) + (x1 - x0)] = False
    paper = np.median(lab[max(0, y0 - 3):min(h, y1 + 3), max(0, x0 - 3):min(w, x1 + 3)][ring], axis=0)
    return np.array([y1 - y0, stroke, sharp, *ink_lab, paper[0]], np.float32)


# smallest spread worth trusting per feature: a 1-unit colour shift on a page where every word has the
# same ink is not 6 standard deviations
FLOOR = np.array([1.0, 0.3, 0.2, 3.0, 1.5, 1.5, 2.0], np.float32)  # height, stroke, sharp, L, a, b, paper L


def _z(value: np.ndarray, population: np.ndarray, cols: slice) -> np.ndarray:
    """Robust distance of a word's features from the population's: |x - median| / (1.4826 * MAD + floor)."""
    med = np.median(population, axis=0)
    mad = 1.4826 * np.median(np.abs(population - med), axis=0) + FLOOR[cols]
    return np.abs(value - med) / mad


class _Chars:
    name = "chars"

    def applies(self, info: ImageInfo) -> bool:
        return True

    def heatmap(self, img: np.ndarray, info: ImageInfo, words) -> np.ndarray | None:
        if not words:
            return None
        grey = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(np.float32)
        rows = [(box, text, f) for box, text in words if (f := _features(img, lab, grey, box)) is not None]
        if len(rows) < MIN_GROUP:
            return None
        feats = np.array([f for _, _, f in rows])
        heat = np.zeros(grey.shape, np.float32)
        for i, (box, text, f) in enumerate(rows):
            if not NUMBER.search(text):
                continue
            # ink and paper colour: compared with every word on the page (a bold line has the same ink)
            z = list(_z(f[3:], feats[:, 3:], slice(3, None)))
            # sharpness: only against words of the same style (height within 15%, stroke within 25%)
            style = (np.abs(feats[:, 0] - f[0]) <= 0.15 * f[0]) & (np.abs(feats[:, 1] - f[1]) <= 0.25 * max(f[1], 1))
            if style.sum() >= MIN_GROUP:
                z += list(_z(f[2:3], feats[style, 2:3], slice(2, 3)))
            top = sorted(z, reverse=True)[:2]
            score = min(1.0, float(np.mean(top)) / 4)
            x0, y0, x1, y1 = (int(round(v)) for v in box)
            heat[max(0, y0):y1, max(0, x0):x1] = np.maximum(heat[max(0, y0):y1, max(0, x0):x1], score)
        return heat


CHARS = _Chars()
