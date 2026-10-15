"""Error level analysis, per word: re-save at a lower quality and measure how much each word changes.
A word with a different compression history (pasted from another source, or added after the photo was
shared) changes more or less than the page's other words."""

import cv2
import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo
from claimlens.pipeline.forensics.words import clip_box, odd_one_out, paint


class _Ela:
    name = "ela"

    def applies(self, info: ImageInfo) -> bool:
        return info.format == "jpeg" and (info.jpeg_quality or 0) >= 50

    def heatmap(self, img: np.ndarray, info: ImageInfo, words) -> np.ndarray | None:
        if not words:
            return None
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        q = max(50, min(75, int(info.jpeg_quality) - 10))
        again = cv2.imdecode(cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR)
        diff = cv2.GaussianBlur(np.abs(bgr.astype(np.float32) - again.astype(np.float32)).max(axis=2), (0, 0), 1)
        boxes = [clip_box(box, img.shape) for box, _ in words]
        values = [float(diff[y0:y1, x0:x1].mean()) if b else None for b in boxes for (x0, y0, x1, y1) in [b or (0, 0, 0, 0)]]
        return paint(img.shape, boxes, odd_one_out(values, spread=2.5))


ELA = _Ela()
