"""JPEG ghost, per word (Farid 2009): a photo saved once at quality q1 barely changes when re-saved at q1.
For each word, find the re-save quality where it changes least. Most words agree on one quality (the
earlier save); a word that doesn't ghost there was put in afterwards."""

import cv2
import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo
from claimlens.pipeline.forensics.words import MIN_WORDS, clip_box, paint


class _Ghost:
    name = "dq"

    def applies(self, info: ImageInfo) -> bool:
        return info.format == "jpeg" and info.qtables is not None and (info.jpeg_quality or 0) >= 60

    def heatmap(self, img: np.ndarray, info: ImageInfo, words) -> np.ndarray | None:
        if len(words) < MIN_WORDS:
            return None
        grey = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        qualities = list(range(50, int(info.jpeg_quality) - 4, 5))
        if len(qualities) < 3:
            return None
        boxes = [clip_box(box, img.shape) for box, _ in words]
        curves = np.zeros((len(boxes), len(qualities)), np.float32)
        for j, q in enumerate(qualities):
            again = cv2.imdecode(cv2.imencode(".jpg", grey, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_GRAYSCALE)
            sq = (grey.astype(np.float32) - again.astype(np.float32)) ** 2
            for i, b in enumerate(boxes):
                if b:
                    x0, y0, x1, y1 = b
                    curves[i, j] = sq[y0:y1, x0:x1].mean()
        valid = [i for i, b in enumerate(boxes) if b]
        # a ghost is a local dip: re-saving at the earlier save's quality changes a word much less than the
        # qualities either side. Find the quality where the page's words dip most, then score each word by
        # how much less it dips there than the page's typical word.
        dips = np.zeros_like(curves)
        for j in range(1, len(qualities) - 1):
            neighbours = np.minimum(curves[:, j - 1], curves[:, j + 1])
            dips[:, j] = 1 - curves[:, j] / (neighbours + 1e-6)
        page_dip = np.median(dips[valid], axis=0)
        star = int(page_dip.argmax())
        typical = float(page_dip[star])
        if typical < 0.3:
            return None  # no earlier save the page agrees on: nothing to compare against
        scores = [float(np.clip(1 - dips[i, star] / typical, 0, 1)) if b else None for i, b in enumerate(boxes)]
        return paint(img.shape, boxes, scores)


DQ = _Ghost()
