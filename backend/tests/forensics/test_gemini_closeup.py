import json

from claimlens.pipeline.forensics.base import field_score, safe_heatmap
from claimlens.pipeline.forensics.gemini_closeup import GeminiCloseup
from claimlens.pipeline.forensics.image import load_image
from tests.forensics.synth import jpeg, page


class FakeVision:
    """Answers per crop: by call order from `answers`, or the same answer for all."""

    def __init__(self, answers):
        self.answers, self.calls = answers, 0

    def ask(self, png: bytes, prompt: str) -> str | None:
        self.calls += 1
        a = self.answers(self.calls) if callable(self.answers) else self.answers
        return a if a is None or isinstance(a, str) else json.dumps(a)


def _setup():
    arr, words, numbers = page()
    img, info = load_image(jpeg(arr, 92))
    return img, info, words, numbers


def test_edited_and_genuine_answers_map_to_scores(tmp_path):
    img, info, words, numbers = _setup()
    ask = lambda n: {"looks_edited": n == 1, "confidence": 0.9, "why": "x"}  # only the first number "edited"
    heat = safe_heatmap(GeminiCloseup(FakeVision(ask), cache_dir=tmp_path), img, info, words)
    scores = [field_score(heat, words[i][0]) for i in numbers]
    assert scores[0] > 0.9 and max(scores[1:]) < 0.1


def test_refusals_and_bad_json_are_unsure(tmp_path):
    img, info, words, numbers = _setup()
    answers = lambda n: None if n % 2 else "not json"
    vision = FakeVision(lambda n: {"looks_edited": True, "confidence": 1.0} if n == 3 else answers(n))
    heat = safe_heatmap(GeminiCloseup(vision, cache_dir=tmp_path), img, info, words)
    scores = [field_score(heat, words[i][0]) for i in numbers]
    assert scores[2] > 0.9 and all(abs(s - 0.5) < 1e-6 for i, s in enumerate(scores) if i != 2)


def test_all_unsure_is_no_opinion(tmp_path):
    img, info, words, _ = _setup()
    assert safe_heatmap(GeminiCloseup(FakeVision(None), cache_dir=tmp_path), img, info, words) is None


def test_at_most_30_numbers_are_asked(tmp_path):
    img, info, words, _ = _setup()
    many = words * 3  # 60 number words (repeats: no cache, so every one would be asked)
    vision = FakeVision({"looks_edited": False, "confidence": 0.8})
    safe_heatmap(GeminiCloseup(vision, cache_dir=None), img, info, many)
    assert vision.calls == 30


def test_answers_are_cached(tmp_path):
    img, info, words, _ = _setup()
    vision = FakeVision({"looks_edited": False, "confidence": 0.8})
    detector = GeminiCloseup(vision, cache_dir=tmp_path)
    safe_heatmap(detector, img, info, words)
    first = vision.calls
    safe_heatmap(detector, img, info, words)
    assert vision.calls == first
