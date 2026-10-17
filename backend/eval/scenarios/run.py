"""Run generated claims through ClaimLens with the real AI (and OCR), locally, and write results.jsonl.

python -m eval.scenarios.run --n 100 --formats one_pdf,split_files,photos --seed 7
Local storage and database (no prod writes, no daily limit); Vertex Gemini and Document AI via gcloud login.
"""

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from claimlens.ai import VertexGemini
from claimlens.ocr import DocAiOcr
from eval.scenarios.forgeries import FORGERIES, pick
from eval.scenarios.recipe import make_recipe
from eval.scenarios.targets import LocalTarget
from eval.scenarios.truth import rules_present, truth_of

PROJECT = "social-pulse-510513"
PROCESSOR = "projects/social-pulse-510513/locations/us/processors/86b3907ea0dbb405"
OUT = Path(__file__).resolve().parents[2] / "data" / "eval" / "scenarios"


def plan(n: int, seed: int, formats: list[str], run: str) -> list[tuple]:
    rng = np.random.default_rng(seed)
    cases = []
    for i in range(n):
        recipe = make_recipe(seed * 10000 + i, run)
        names = pick(rng, recipe)
        for name in names:
            recipe = FORGERIES[name].apply(recipe)
        cases.append((seed * 10000 + i, names, formats[i % len(formats)], recipe))
    return cases


def main(n: int, seed: int, formats: list[str], workers: int, offline: bool = False) -> Path:
    """`offline`: the AI stand-in that reads the true facts, and no OCR (photos stay unreadable)."""
    run = f"{'offline' if offline else 'live'}{int(time.time())}"
    folder = OUT / run
    folder.mkdir(parents=True, exist_ok=True)
    ocr = None if offline else DocAiOcr(PROJECT, "us", PROCESSOR)
    targets = [LocalTarget(folder / f"w{w}", ocr=ocr, ai_factory=None if offline else
                           lambda: VertexGemini(PROJECT, "global", "gemini-2.5-flash")) for w in range(workers)]

    def one(job):
        k, (case_seed, names, fmt, recipe) = job
        truth = truth_of(recipe, names, fmt, ocr=not offline)
        try:
            res = targets[k % workers].run(recipe, names, fmt, truth)
            error, found, status, band, payable, secs, cid, advice = (
                res.error, dict(res.codes), res.status, res.band, res.payable, res.seconds, res.case_id,
                res.recommendation)
        except Exception as e:  # one broken case never stops the run
            error, found, status, band, payable, secs, cid, advice = (
                f"{type(e).__name__}: {e}", {}, None, None, None, 0, None, None)
        row = {"seed": case_seed, "forgeries": names, "fmt": fmt, "expected_codes": dict(truth.codes),
               "found_codes": found, "status_expected": truth.status, "status_found": status,
               "band_expected": truth.band, "band_found": band, "payable_expected": truth.payable,
               "payable_found": payable, "rules": rules_present(recipe), "recommendation_expected": truth.recommendation,
               "recommendation_found": advice, "error": error, "seconds": secs, "case_id": cid}
        logging.info("seed %s %s %s -> %s", case_seed, fmt, names or ["clean"], status)
        return row

    with ThreadPoolExecutor(workers) as pool:
        rows = list(pool.map(one, enumerate(plan(n, seed, formats, run))))
    (folder / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return folder / "results.jsonl"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "claimlens.request", "google_genai.models"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--formats", default="one_pdf,split_files,photos")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--offline", action="store_true", help="use the true-facts AI stand-in instead of Gemini and OCR")
    args = ap.parse_args()
    print(main(args.n, args.seed, args.formats.split(","), args.workers, args.offline))
