"""Copy-move: a digit or stamp copied from elsewhere on the same page.

Documents repeat glyphs everywhere, so a match alone means nothing; a real copy is nearly pixel-identical
to its source at one exact shift, closer than two genuine prints of the same glyph. JPEG compression
re-noises a copy enough to hide that below about quality 93 (measured), so lossy-compressed photos get no
opinion rather than a guess."""

from collections import defaultdict

import cv2
import numpy as np

from claimlens.pipeline.forensics.image import ImageInfo

PATCH = 2  # pad around the matched keypoints: tight, so pixels that were not copied stay out
MIN_SHIFT = 20
MIN_CLUSTER = 4
MAX_AREA = 0.05  # a copy is a digit, a stamp, a signature: not a block of the page
CLOSER = 0.75  # a copy must be this much closer to its source than genuine repeats are to each other


def _aligned_mad(grey: np.ndarray, box, dx: int, dy: int) -> float | None:
    h, w = grey.shape
    x0, y0, x1, y1 = (int(v) for v in box)
    if x0 < 1 or y0 < 1 or x1 > w - 1 or y1 > h - 1:
        return None
    a, best = grey[y0:y1, x0:x1], None
    for ex in (-1, 0, 1):
        for ey in (-1, 0, 1):
            ty0, tx0 = y0 + dy + ey, x0 + dx + ex
            if tx0 < 0 or ty0 < 0 or tx0 + (x1 - x0) > w or ty0 + (y1 - y0) > h:
                continue
            mad = float(np.abs(a - grey[ty0:ty0 + (y1 - y0), tx0:tx0 + (x1 - x0)]).mean())
            best = mad if best is None else min(best, mad)
    return best


def _areas(points: list, radius: float = 40) -> list[list]:
    """Group matches whose source points lie close together (single linkage)."""
    parent = list(range(len(points)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    src = np.array([s for s, _ in points])
    for i in range(len(points)):
        near = np.where(np.linalg.norm(src[i + 1:] - src[i], axis=1) < radius)[0] + i + 1
        for j in near:
            parent[root(int(j))] = root(i)
    groups: dict[int, list] = {}
    for i, p in enumerate(points):
        groups.setdefault(root(i), []).append(p)
    return list(groups.values())


def pairs(img: np.ndarray) -> list[tuple[tuple, tuple]]:
    """(source box, target box) for each area that reappears, near pixel-identical, at one shift."""
    grey8 = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    kps, desc = cv2.ORB_create(nfeatures=4000).detectAndCompute(grey8, None)
    if desc is None or len(kps) < MIN_CLUSTER * 2:
        return []
    grey = grey8.astype(np.float32)
    h, w = grey.shape
    shifts = defaultdict(list)
    for group in cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(desc, desc, k=4):
        for m in group[1:]:
            if m.distance >= 40:
                continue
            p, q = np.array(kps[m.queryIdx].pt), np.array(kps[m.trainIdx].pt)
            if np.linalg.norm(p - q) < MIN_SHIFT:
                continue
            src, dst = (p, q) if (p[1], p[0]) < (q[1], q[0]) else (q, p)
            shifts[tuple(np.round((dst - src) / 4).astype(int))].append((src, dst))
    clusters = []
    for group in shifts.values():
        for points in _areas(group):  # one shift is shared by every line of a template: split by place
            if len(points) >= MIN_CLUSTER:
                clusters.append(points)
    measured = []
    for points in clusters:
        src = np.array([s for s, _ in points])
        shift = np.round(np.median(np.array([d - s for s, d in points]), axis=0)).astype(int)
        box = (src[:, 0].min() - PATCH, src[:, 1].min() - PATCH, src[:, 0].max() + PATCH, src[:, 1].max() + PATCH)
        if (box[2] - box[0]) * (box[3] - box[1]) > MAX_AREA * h * w:
            continue
        mad = _aligned_mad(grey, box, int(shift[0]), int(shift[1]))
        if mad is not None:
            measured.append((mad, box, shift))
    if len(measured) < 3:
        return []  # nothing to compare against: how alike genuine repeats are on this page is unknown
    typical = float(np.median([m for m, _, _ in measured]))
    out = []
    for mad, box, (dx, dy) in measured:
        if mad < CLOSER * typical:
            out.append((tuple(map(float, box)), (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)))
    return out


class _CopyMove:
    name = "copymove"

    def applies(self, info: ImageInfo) -> bool:
        return info.format == "png" or (info.format == "jpeg" and (info.jpeg_quality or 0) >= 93)

    def heatmap(self, img: np.ndarray, info: ImageInfo, words) -> np.ndarray | None:
        heat = np.zeros(img.shape[:2], np.float32)
        for src, dst in pairs(img):
            for x0, y0, x1, y1 in (src, dst):
                heat[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)] = 1.0
        return heat


COPYMOVE = _CopyMove()
