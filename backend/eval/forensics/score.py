"""Score every detector on the forensics test set, per field, and the metrics that decide what ships.

python -m eval.forensics.score [--gemini] [--catnet <folder of .npy>]
"""

import argparse
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from claimlens.pipeline.forensics.base import field_score, safe_heatmap
from claimlens.pipeline.forensics.chars import CHARS
from claimlens.pipeline.forensics.copymove import COPYMOVE
from claimlens.pipeline.forensics.dq import DQ
from claimlens.pipeline.forensics.ela import ELA
from claimlens.pipeline.forensics.image import load_image
from claimlens.pipeline.forensics.noise import NOISE

log = logging.getLogger(__name__)
SET = Path(__file__).resolve().parents[2] / "data" / "eval" / "forensics"
NUMBER_KINDS = {"amount", "date", "invoice"}
SPLIT_SEED = 7
MAX_FPR = 0.05
MIN_AUC = 0.70


def _auc(pos: np.ndarray, neg: np.ndarray) -> float | None:
    """P(a forged field scores above a genuine one), ties counting half (Mann-Whitney)."""
    if len(pos) == 0 or len(neg) == 0:
        return None
    values = np.concatenate([pos, neg])
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values))
    sorted_values = values[order]
    i = 0
    while i < len(values):  # average ranks over ties
        j = i
        while j + 1 < len(values) and sorted_values[j + 1] == sorted_values[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _threshold(negatives: np.ndarray) -> float | None:
    """The smallest score t with at most 5% of these genuine numbers at or above it (ties handled)."""
    if len(negatives) == 0:
        return None
    for t in np.unique(negatives):
        if (negatives >= t).mean() <= MAX_FPR:
            return float(t)
    return float(np.nextafter(negatives.max(), np.inf))


def _halves(bases: set) -> tuple[set, set]:
    ordered = sorted(bases)
    perm = np.random.default_rng(SPLIT_SEED).permutation(len(ordered))
    a = {ordered[i] for i in perm[: len(ordered) // 2]}
    return a, set(ordered) - a


def metrics(rows: list[dict], detector: str, kinds: tuple[str, ...]) -> dict:
    """Field-level metrics for one detector on the given forgery kinds.

    Positives: edited fields of those kinds. Negatives: every unedited number field (on controls and on forged
    images). The threshold is fixed on half A of the bills (5% false positives) and everything is reported on
    half B. No-opinion rows are counted, never treated as negatives.
    """
    mine = [r for r in rows if r["detector"] == detector]
    relevant = [r for r in mine if (r["edited"] and r["kind"] in kinds) or
                (not r["edited"] and r.get("field_kind", "amount") in NUMBER_KINDS)]
    no_opinion = sum(1 for r in relevant if r["score"] is None)
    scored = [r for r in relevant if r["score"] is not None]
    half_a, half_b = _halves({r["base"] for r in mine})
    # the operating point is set on ordinary genuine numbers only, so an odd genuine condition (a re-save, a
    # bold line) can't raise the threshold above itself and hide its own false positives
    neg_a = np.array([r["score"] for r in scored if not r["edited"] and r["base"] in half_a
                      and r["control_type"] in (None, "original")])
    threshold = _threshold(neg_a)
    pos_b = np.array([r["score"] for r in scored if r["edited"] and r["base"] in half_b])
    neg_b = np.array([r["score"] for r in scored if not r["edited"] and r["base"] in half_b])
    fpr_by_control = {}
    for r in scored:
        if r["kind"] == "control" and r["base"] in half_b and not r["edited"]:
            fpr_by_control.setdefault(r["control_type"], []).append(r["score"])
    return {
        "detector": detector, "kinds": kinds, "auc": _auc(pos_b, neg_b), "threshold": threshold,
        "tpr_at_5fpr": float((pos_b >= threshold).mean()) if threshold is not None and len(pos_b) else None,
        "fpr_by_control": {k: float((np.array(v) >= threshold).mean()) if threshold is not None else None
                           for k, v in sorted(fpr_by_control.items())},
        "n_pos": int(len(pos_b)), "n_neg": int(len(neg_b)), "n_no_opinion": no_opinion, "half_b": half_b,
    }


def keep(m: dict) -> bool:
    """Ship a detector only if it separates forgeries (AUC >= 0.70) and stays quiet on every genuine condition."""
    fprs = [v for v in m["fpr_by_control"].values() if v is not None]
    return m["auc"] is not None and m["auc"] >= MIN_AUC and bool(fprs) and max(fprs) <= MAX_FPR


def fused(rows: list[dict], detectors: list[str]) -> list[dict]:
    """Per field, the max and the mean of the given detectors' scores (missing ones ignored)."""
    by_field: dict[tuple, list] = {}
    for r in rows:
        if r["detector"] in detectors:
            by_field.setdefault((r["image"], r["field"]), []).append(r)
    out = []
    for group in by_field.values():
        scores = [r["score"] for r in group if r["score"] is not None]
        base = {k: v for k, v in group[0].items() if k not in ("detector", "score", "seconds")}
        out.append({**base, "detector": "fused_max", "score": max(scores) if scores else None})
        out.append({**base, "detector": "fused_mean", "score": float(np.mean(scores)) if scores else None})
    return out


def score_set(set_dir: Path, gemini=None, catnet_dir: Path | None = None) -> list[dict]:
    """Run every detector on every image of the manifest; one row per (image, field, detector)."""
    detectors = [ELA, NOISE, DQ, COPYMOVE, CHARS] + ([gemini] if gemini else [])
    rows = []
    for line in (set_dir / "manifest.jsonl").read_text().splitlines():
        entry = json.loads(line)
        img, info = load_image((set_dir / entry["image"]).read_bytes())
        if img is None:
            continue
        s = info.scale
        words = [([v * s for v in f["box"]], f["value"]) for f in entry["fields"]]
        heats = {}
        for d in detectors:
            started = time.time()
            heats[d.name] = (safe_heatmap(d, img, info, words), time.time() - started)
        npy = catnet_dir / (Path(entry["image"]).stem + ".npy") if catnet_dir else None
        if npy is not None:
            heat = None
            if npy.is_file():
                heat = cv2.resize(np.load(npy).astype(np.float32), (img.shape[1], img.shape[0]))
            took = catnet_dir / (Path(entry["image"]).stem + ".time")
            heats["catnet"] = (heat, float(took.read_text()) if took.is_file() else None)
        for f, (box, _) in zip(entry["fields"], words):
            if f["kind"] == "text":
                continue
            for name, (heat, seconds) in heats.items():
                rows.append({"image": entry["image"], "base": entry["base"], "kind": entry["kind"],
                             "control_type": entry.get("control_type"), "field": f["name"],
                             "field_kind": f["kind"], "edited": f["edited"], "detector": name,
                             "score": None if heat is None else field_score(heat, box), "seconds": seconds})
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini", action="store_true")
    ap.add_argument("--catnet", type=Path)
    args = ap.parse_args()
    gemini = None
    if args.gemini:
        from claimlens.pipeline.forensics.gemini_closeup import GeminiCloseup, GeminiVision

        gemini = GeminiCloseup(GeminiVision("social-pulse-510513"), cache_dir=SET / "closeup-cache")
    results = score_set(SET, gemini, args.catnet)
    (SET / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results))
    print(f"{len(results)} rows -> {SET / 'results.jsonl'}")
