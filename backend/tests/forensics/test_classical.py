import numpy as np
from PIL import Image, ImageFilter

from claimlens.pipeline.forensics.base import field_score, safe_heatmap
from claimlens.pipeline.forensics.chars import CHARS
from claimlens.pipeline.forensics.copymove import COPYMOVE, pairs
from claimlens.pipeline.forensics.dq import DQ
from claimlens.pipeline.forensics.ela import ELA
from claimlens.pipeline.forensics.image import load_image
from claimlens.pipeline.forensics.noise import NOISE
from tests.forensics.synth import decode, jpeg, page, png, retype

TARGET = 5  # the number word we tamper with


def _scores(detector, data: bytes, words, numbers):
    img, info = load_image(data)
    heat = safe_heatmap(detector, img, info, words)
    assert heat is not None, f"{detector.name} gave no opinion"
    return [field_score(heat, words[i][0]) for i in numbers]


def _others(scores, numbers):
    return [s for s, i in zip(scores, numbers) if i != numbers[TARGET]]


def _paste(base, src, box, pad=4):
    x0, y0, x1, y1 = box
    base[y0 - pad:y1 + pad, x0 - pad:x1 + pad] = src[y0 - pad:y1 + pad, x0 - pad:x1 + pad]
    return base


def test_ela_flags_a_patch_with_a_different_compression_history():
    arr, words, numbers = page()
    box = words[numbers[TARGET]][0]
    # a photo shared once (q75), then a fresh number pasted in and saved at q90
    shared = _paste(decode(jpeg(arr, 75)), arr, box)
    scores = _scores(ELA, jpeg(shared, 90), words, numbers)
    assert scores[TARGET] > 0.5 and np.median(_others(scores, numbers)) < 0.2
    # the other direction: a fresh photo with a number cut from a low-quality (q60) source
    pasted = _paste(arr.copy(), decode(jpeg(arr, 60)), box)
    scores = _scores(ELA, jpeg(pasted, 90), words, numbers)
    assert scores[TARGET] > 0.5 and np.median(_others(scores, numbers)) < 0.2


def test_noise_flags_a_smoothed_patch():
    arr, words, numbers = page()
    x0, y0, x1, y1 = words[numbers[TARGET]][0]
    region = Image.fromarray(arr[y0 - 6:y1 + 6, x0 - 6:x1 + 6]).filter(ImageFilter.GaussianBlur(2))
    arr[y0 - 6:y1 + 6, x0 - 6:x1 + 6] = np.asarray(region)  # inpainting leaves the area too smooth
    scores = _scores(NOISE, jpeg(arr, 92), words, numbers)
    assert scores[TARGET] > 0.5 and np.median(_others(scores, numbers)) < 0.2


def test_dq_ghost_flags_a_once_compressed_patch():
    arr, words, numbers = page()
    earlier = decode(jpeg(arr, 75))  # the photo was saved at 75 once before
    x0, y0, x1, y1 = words[numbers[TARGET]][0]
    earlier[y0 - 8:y1 + 8, x0 - 8:x1 + 8] = arr[y0 - 8:y1 + 8, x0 - 8:x1 + 8]  # pasted from an uncompressed source
    scores = _scores(DQ, jpeg(earlier, 90), words, numbers)
    assert scores[TARGET] > 0.5 and np.median(_others(scores, numbers)) < 0.2


def test_copymove_is_safe_and_only_judges_near_lossless_images():
    # its detection quality is measured on the forged set (keep rule), not asserted here
    arr, words, numbers = page()
    sx0, sy0, sx1, sy1 = words[numbers[2]][0]
    tx0, ty0 = words[numbers[TARGET]][0][:2]
    arr[ty0:ty0 + (sy1 - sy0), tx0:tx0 + (sx1 - sx0)] = arr[sy0:sy1, sx0:sx1]
    img, info = load_image(jpeg(arr, 90))
    assert safe_heatmap(COPYMOVE, img, info, words) is None  # ordinary phone JPEG: no opinion
    img, info = load_image(jpeg(arr, 95))
    heat = safe_heatmap(COPYMOVE, img, info, words)
    assert heat is not None and heat.shape == img.shape[:2]
    assert all(len(p) == 2 and len(p[0]) == 4 for p in pairs(img))
    img, info = load_image(png(arr))
    assert safe_heatmap(COPYMOVE, img, info, words) is not None


def test_chars_flags_a_retyped_number():
    arr, words, numbers = page()
    arr = retype(arr, words[numbers[TARGET]][0], "9,999")
    scores = _scores(CHARS, jpeg(arr, 92), words, numbers)
    assert scores[TARGET] == max(scores) and scores[TARGET] > 0.5


def test_chars_does_not_flag_a_genuine_bold_total():
    arr, words, numbers = page(bold_total=True)
    scores = _scores(CHARS, jpeg(arr, 92), words, numbers)
    assert scores[-1] < 0.5  # the bold TOTAL amount is a style, not an edit


def test_word_level_detectors_need_words():
    arr, _, _ = page()
    img, info = load_image(jpeg(arr, 90))
    for detector in (ELA, NOISE, DQ):
        assert safe_heatmap(detector, img, info, []) is None, detector.name


def test_jpeg_only_detectors_have_no_opinion_on_png():
    arr, words, _ = page()
    img, info = load_image(png(arr))
    assert safe_heatmap(DQ, img, info, words) is None
    assert safe_heatmap(ELA, img, info, words) is None
    assert safe_heatmap(NOISE, img, info, words) is not None


def test_very_compressed_jpeg_no_opinion():
    arr, words, _ = page()
    img, info = load_image(jpeg(arr, 40))
    assert safe_heatmap(DQ, img, info, words) is None
    assert safe_heatmap(ELA, img, info, words) is None


def test_chars_needs_words():
    arr, _, _ = page()
    img, info = load_image(jpeg(arr, 90))
    assert safe_heatmap(CHARS, img, info, []) is None


def test_blank_page_never_raises_and_flags_nothing():
    blank = np.full((1100, 1400, 3), 246, np.uint8)
    img, info = load_image(jpeg(blank, 90))
    for detector in (ELA, NOISE, DQ, COPYMOVE, CHARS):
        heat = safe_heatmap(detector, img, info, [])
        assert heat is None or heat.max() < 0.2, detector.name
