"""Turn a rendered bill into something like a phone photo, and the ways genuine photos get changed."""

import io

import cv2
import numpy as np
from PIL import Image


def _decode(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).copy()


def _jpeg(arr: np.ndarray, quality: int) -> bytes:
    out = io.BytesIO()
    Image.fromarray(arr).save(out, "JPEG", quality=int(quality))
    return out.getvalue()


def transform_box(box, matrix: np.ndarray) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    pts = np.array([[[x0, y0]], [[x1, y0]], [[x0, y1]], [[x1, y1]]], np.float32)
    out = cv2.perspectiveTransform(pts, matrix.astype(np.float32)).reshape(-1, 2)
    return float(out[:, 0].min()), float(out[:, 1].min()), float(out[:, 0].max()), float(out[:, 1].max())


def to_photo(png: bytes, seed: int) -> tuple[bytes, np.ndarray, int]:
    """(JPEG bytes, homography from bill to photo pixels, JPEG quality). Slight tilt, light, blur, grain."""
    rng = np.random.default_rng(seed)
    img = _decode(png).astype(np.float32)
    h, w = img.shape[:2]
    jitter = lambda: rng.uniform(-0.025, 0.025)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[w * jitter(), h * jitter()], [w * (1 + jitter()), h * jitter()],
                      [w * (1 + jitter()), h * (1 + jitter())], [w * jitter(), h * (1 + jitter())]])
    dst -= dst.min(axis=0)
    size = (int(dst[:, 0].max()), int(dst[:, 1].max()))
    matrix = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(img, matrix, size, borderValue=(90, 90, 95))
    photo = photo * rng.uniform(0.9, 1.05) + rng.uniform(-10, 8)
    photo = cv2.GaussianBlur(photo, (0, 0), rng.uniform(0.3, 0.8))
    photo += rng.normal(0, rng.uniform(2, 4), photo.shape)
    quality = int(rng.integers(85, 96))
    return _jpeg(np.clip(photo, 0, 255).astype(np.uint8), quality), matrix, quality


def whatsapp(jpg: bytes) -> tuple[bytes, float]:
    """Shared over a chat app: long side 1600, quality 70. Returns (bytes, scale)."""
    img = Image.open(io.BytesIO(jpg)).convert("RGB")
    scale = min(1.0, 1600 / max(img.size))
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=70)
    return out.getvalue(), scale


def screenshot(jpg: bytes) -> bytes:
    out = io.BytesIO()
    Image.open(io.BytesIO(jpg)).convert("RGB").save(out, "PNG")
    return out.getvalue()


def crease_shadow(jpg: bytes, seed: int, quality: int) -> bytes:
    """A fold line and a soft shadow across the page."""
    rng = np.random.default_rng(seed)
    img = _decode(jpg).astype(np.float32)
    h, w = img.shape[:2]
    ramp = np.linspace(rng.uniform(0.75, 0.9), 1.0, w, dtype=np.float32)
    img *= ramp[None, :, None]
    y = int(rng.uniform(0.3, 0.7) * h)
    img[y - 2:y + 2] *= 0.85
    return _jpeg(np.clip(img, 0, 255).astype(np.uint8), quality)
