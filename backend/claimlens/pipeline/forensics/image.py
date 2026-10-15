"""Load an uploaded image the way a person sees it (EXIF-rotated), small enough to analyse, with its JPEG facts."""

import io
import warnings
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 4096
# IJG standard luminance table: JPEG quality q scales it, so the ratio estimates q
STD_LUMA_MEAN = float(np.mean([
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]))


@dataclass
class ImageInfo:
    format: str  # jpeg, png or other
    jpeg_quality: int | None
    qtables: list[np.ndarray] | None
    oriented: bool  # an EXIF rotation was applied
    original_size: tuple[int, int]  # (width, height) as displayed
    size: tuple[int, int]  # (width, height) analysed
    scale: float  # analysed pixels per original pixel


def _quality(table) -> int:
    scale = 100 * float(np.mean(table)) / STD_LUMA_MEAN
    q = (200 - scale) / 2 if scale <= 100 else 5000 / scale
    return int(round(min(100, max(1, q))))


def load_image(data: bytes) -> tuple[np.ndarray | None, ImageInfo | None]:
    """RGB uint8 array (long side at most 4096) and what we know about the file, or (None, None)."""
    try:
        with warnings.catch_warnings():
            # large phone photos trip Pillow's bomb *warning*; its hard limit (an error) still applies
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            return _load(data)
    except Exception:
        return None, None


def _load(data: bytes) -> tuple[np.ndarray, ImageInfo]:
    img = Image.open(io.BytesIO(data))
    fmt = {"JPEG": "jpeg", "PNG": "png"}.get(img.format or "", "other")
    tables = getattr(img, "quantization", None) if fmt == "jpeg" else None
    orientation = img.getexif().get(0x0112, 1)
    w, h = img.size
    shown = (h, w) if orientation in (5, 6, 7, 8) else (w, h)
    if fmt == "jpeg":
        img.draft("RGB", (MAX_SIDE, MAX_SIDE))  # decode at a reduced scale: a 100 MP photo never fully decoded
    img.load()
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > MAX_SIDE:
        factor = MAX_SIDE / max(img.size)
        img = img.resize((round(img.width * factor), round(img.height * factor)), Image.LANCZOS)
    array = np.asarray(img)
    qtables = [np.asarray(t, dtype=np.float32) for t in tables.values()] if tables else None
    return array, ImageInfo(
    format=fmt, jpeg_quality=_quality(qtables[0]) if qtables else None, qtables=qtables,
    oriented=orientation in (2, 3, 4, 5, 6, 7, 8), original_size=shown,
    size=(array.shape[1], array.shape[0]), scale=array.shape[1] / shown[0])
