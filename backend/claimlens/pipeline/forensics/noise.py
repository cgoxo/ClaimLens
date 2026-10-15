"""Noise inconsistency, per word: a camera leaves grain on the paper between the strokes. An inpainted or
pasted number has smoother, or differently grained, paper than the page's other words."""

import cv2
import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo
from claimlens.pipeline.forensics.words import clip_box, odd_one_out, paint

MARGIN = 6
MIN_PAPER = 30  # paper pixels needed to estimate the grain around a word


class _Noise:
    name = "noise"

    def applies(self, info: ImageInfo) -> bool:
        return True

    def heatmap(self, img: np.ndarray, info: ImageInfo, words) -> np.ndarray | None:
        if not words:
            return None
        grey = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        residual = grey.astype(np.float32) - cv2.medianBlur(grey, 3).astype(np.float32)
        boxes, values = [], []
        for box, _ in words:
            b = clip_box((box[0] - MARGIN, box[1] - MARGIN, box[2] + MARGIN, box[3] + MARGIN), img.shape)
            boxes.append(b)
            if b is None:
                values.append(None)
                continue
            x0, y0, x1, y1 = b
            region = grey[y0:y1, x0:x1]
            ink = (region < np.percentile(region, 90) - 20).astype(np.uint8)
            paper = cv2.dilate(ink, np.ones((5, 5), np.uint8)) == 0
            r = residual[y0:y1, x0:x1][paper]
            values.append(float(r.std()) if r.size >= MIN_PAPER and r.std() > 0.05 else None)
        return paint(img.shape, boxes, odd_one_out(values, spread=2.0))


NOISE = _Noise()
