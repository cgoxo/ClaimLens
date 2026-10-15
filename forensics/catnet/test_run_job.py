"""Runs inside the built image, on CPU, in the Cloud Build step after the build (before the push)."""

import io
import json
import os

import numpy as np
from PIL import Image, ImageDraw

import run_job


def _page() -> np.ndarray:
    rng = np.random.default_rng(1)
    img = Image.new("RGB", (512, 384), (240, 238, 232))
    d = ImageDraw.Draw(img)
    for i in range(12):
        d.text((30, 20 + 28 * i), f"Line {i} charges   Rs {int(rng.integers(100, 9000)):,}", fill=(30, 30, 35))
    arr = np.asarray(img).astype(np.float32) + rng.normal(0, 3, (384, 512, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def _save(arr, path, **kw):
    Image.fromarray(arr).save(path, **kw)


def test_heatmaps_match_images_and_non_jpegs_are_na(tmp_path):
    images, out = tmp_path / "images", tmp_path / "out"
    images.mkdir()
    page = _page()
    _save(page, images / "genuine.jpg", quality=90)
    patched = np.asarray(Image.open(io.BytesIO(_jpeg(page, 60)))).copy()
    edited = page.copy()
    edited[150:230, 200:330] = patched[150:230, 200:330]  # an area from a q60 copy, then saved at q90
    _save(edited, images / "patched.jpg", quality=90)
    _save(page, images / "shot.png")
    os.environ["CLOUD_RUN_EXECUTION"] = "test-exec"
    run_job.main(["--images", str(images), "--out", str(out)])
    done = json.loads((out / "done.json").read_text())
    assert done["execution"] == "test-exec"
    assert sorted(done["ok"]) == ["genuine.jpg", "patched.jpg"] and done["na"] == ["shot.png"]
    for name in ("genuine", "patched"):
        heat = np.load(out / f"{name}.npy")
        assert heat.shape == (384, 512) and heat.dtype == np.float16
        assert 0 <= float(heat.min()) and float(heat.max()) <= 1
    heat = np.load(out / "patched.npy").astype(np.float32)
    assert heat[150:230, 200:330].mean() > heat.mean()  # smoke: the patch is hotter than the page on average


def _jpeg(arr, q):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=q)
    return buf.getvalue()
