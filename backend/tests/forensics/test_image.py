import io
import tracemalloc

import numpy as np
from PIL import Image

from claimlens.pipeline.forensics.base import field_score, safe_heatmap
from claimlens.pipeline.forensics.image import load_image


def _jpeg(img: Image.Image, **kw) -> bytes:
    out = io.BytesIO()
    img.save(out, "JPEG", **kw)
    return out.getvalue()


def _page(w=1200, h=900) -> Image.Image:
    return Image.new("RGB", (w, h), "white")


def test_jpeg_info():
    img, info = load_image(_jpeg(_page(), quality=90))
    assert info.format == "jpeg" and 85 <= info.jpeg_quality <= 95
    assert img.shape == (900, 1200, 3) and info.qtables is not None


def test_png_info():
    out = io.BytesIO()
    _page().save(out, "PNG")
    _, info = load_image(out.getvalue())
    assert info.format == "png" and info.qtables is None and info.jpeg_quality is None


def test_exif_orientation_lines_up():
    page = _page(800, 600)
    page.paste((255, 0, 0), (0, 0, 100, 100))  # red square top-left, as stored
    exif = Image.Exif()
    exif[0x0112] = 6  # display rotated 90° clockwise
    img, info = load_image(_jpeg(page, quality=95, exif=exif))
    assert info.oriented and img.shape[:2] == (800, 600)
    # after rotating 90° clockwise, the stored top-left corner shows at the top-right
    assert img[50, 550, 0] > 200 and img[50, 550, 1] < 60


def test_huge_downscaled_within_memory():
    big = _jpeg(Image.new("RGB", (9000, 12000), "white"), quality=85)
    tracemalloc.start()
    img, info = load_image(big)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert max(img.shape[:2]) == 4096 and abs(info.scale - 4096 / 12000) < 1e-3
    assert info.original_size == (9000, 12000)
    assert peak < 1.5 * 1024**3


def test_cmyk_grey_progressive_load_as_rgb():
    for img_in, kw in ((Image.new("CMYK", (700, 700)), {}), (Image.new("L", (700, 700), 200), {}),
                       (_page(700, 700), {"progressive": True})):
        img, info = load_image(_jpeg(img_in, quality=90, **kw))
        assert img.shape == (700, 700, 3) and info.format == "jpeg"


def test_corrupt_gives_nothing():
    assert load_image(_jpeg(_page(), quality=90)[:300]) == (None, None)
    assert load_image(b"not an image") == (None, None)


class _Fixed:
    name = "fixed"

    def __init__(self, result=None, raises=False, applies=True):
        self.result, self.raises, self._applies = result, raises, applies

    def applies(self, info):
        return self._applies

    def heatmap(self, img, info, words):
        if self.raises:
            raise RuntimeError("boom")
        return self.result if self.result is not None else np.zeros(img.shape[:2])


def test_safe_heatmap_no_opinion_cases():
    small, small_info = load_image(_jpeg(_page(400, 300), quality=90))
    assert safe_heatmap(_Fixed(), small, small_info, []) is None  # too small to judge
    img, info = load_image(_jpeg(_page(), quality=90))
    assert safe_heatmap(_Fixed(raises=True), img, info, []) is None
    assert safe_heatmap(_Fixed(result=np.zeros((10, 10))), img, info, []) is None  # wrong shape
    assert safe_heatmap(_Fixed(applies=False), img, info, []) is None
    assert safe_heatmap(_Fixed(), img, info, []).shape == (900, 1200)


def test_field_score():
    heat = np.zeros((200, 200))
    heat[50:70, 50:90] = 1.0
    assert field_score(heat, (50, 50, 90, 70)) == 1.0
    assert field_score(heat, (110, 110, 150, 130)) == 0.0
