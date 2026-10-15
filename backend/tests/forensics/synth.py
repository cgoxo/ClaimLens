"""Synthetic phone-like pages for detector tests: text lines on paper, with sensor noise, saved as JPEG."""

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.load_default(size=28)
BOLD = ImageFont.load_default(size=34)


def page(seed: int = 1, w: int = 1400, h: int = 1100, bold_total: bool = False, noise: float = 3.0):
    """(RGB uint8 array, words [(box, text)], number word indexes). Twenty lines like a bill."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (w, h), (246, 244, 238))
    draw = ImageDraw.Draw(img)
    words, numbers = [], []
    for i in range(20):
        y = 40 + i * 50
        label = f"Item {i + 1} medicines and care"
        amount = f"{int(rng.integers(100, 9000)):,}"
        font = BOLD if bold_total and i == 19 else FONT
        if bold_total and i == 19:
            label = "TOTAL"
        for x, text in ((60, label), (900, "Rs"), (960, amount)):
            draw.text((x, y), text, fill=(30, 30, 35), font=font)
            box = draw.textbbox((x, y), text, font=font)
            words.append((box, text))
            if text == amount:
                numbers.append(len(words) - 1)
    arr = np.asarray(img).astype(np.float32)
    arr += rng.normal(0, noise, arr.shape)
    return np.clip(arr, 0, 255).astype(np.uint8), words, numbers


def jpeg(arr: np.ndarray, quality: int) -> bytes:
    out = io.BytesIO()
    Image.fromarray(arr).save(out, "JPEG", quality=quality)
    return out.getvalue()


def png(arr: np.ndarray) -> bytes:
    out = io.BytesIO()
    Image.fromarray(arr).save(out, "PNG")
    return out.getvalue()


def decode(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).copy()


def retype(arr: np.ndarray, box, text: str, color=(70, 40, 40), size=30) -> np.ndarray:
    """Paint paper over a number and type a new one in a different ink and size: a classic forgery."""
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    draw.rectangle((box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2), fill=(246, 244, 238))
    draw.text((box[0], box[1] - 2), text, fill=color, font=ImageFont.load_default(size=size))
    return np.asarray(img).copy()
