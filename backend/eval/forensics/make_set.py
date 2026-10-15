"""Build the forensics test set: genuine phone photos of fictional bills in several conditions, and forgeries
of one field each. Writes images and manifest.jsonl (ground truth) under `out`.

python -m eval.forensics.make_set --bases 40 --seed 7
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from eval.forensics import forge
from eval.forensics.bills import money, render_bill
from eval.forensics.photo import crease_shadow, screenshot, to_photo, transform_box, whatsapp

log = logging.getLogger(__name__)
OUT = Path(__file__).resolve().parents[2] / "data" / "eval" / "forensics"


def _fields(bill, matrix, scale=1.0, edited=()):
    return [{"name": f.name, "kind": f.kind, "value": f.value, "edited": f.name in edited,
             "box": [v * scale for v in transform_box(f.box, matrix)]} for f in bill.fields]


def main(n_bases: int = 40, seed: int = 7, out: Path = OUT, gemini: forge.ImageEditor | None = None) -> Path:
    out = Path(out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    rows, discarded = [], []

    def save(row_id, data: bytes, ext: str, row: dict):
        path = f"images/{row_id}.{ext}"
        (out / path).write_bytes(data)
        rows.append({"id": row_id, "image": path, **row})

    for b in range(n_bases):
        rng = np.random.default_rng(seed * 1000 + b)
        bill = render_bill(seed * 1000 + b)
        jpg, matrix, q = to_photo(bill.png, seed * 1000 + b)
        base = {"base": b}
        save(f"b{b}-original", jpg, "jpg", {**base, "kind": "control", "control_type": "original",
                                             "fields": _fields(bill, matrix)})
        shared, scale = whatsapp(jpg)
        save(f"b{b}-whatsapp", shared, "jpg", {**base, "kind": "control", "control_type": "whatsapp",
                                                "fields": _fields(bill, matrix, scale)})
        save(f"b{b}-screenshot", screenshot(jpg), "png", {**base, "kind": "control", "control_type": "screenshot",
                                                          "fields": _fields(bill, matrix)})
        jpg2, matrix2, _ = to_photo(bill.png, seed * 1000 + b + 500)
        save(f"b{b}-second", jpg2, "jpg", {**base, "kind": "control", "control_type": "second_photo",
                                            "fields": _fields(bill, matrix2)})
        save(f"b{b}-crease", crease_shadow(jpg, b, q), "jpg", {**base, "kind": "control",
                                                               "control_type": "crease_shadow",
                                                               "fields": _fields(bill, matrix)})

        total = next(f for f in bill.fields if f.name == "total")
        total_box = transform_box(total.box, matrix)
        delta = int(rng.integers(5, 50)) * 100
        new_total = money(sum(a for _, a in bill.items) + delta)
        forgeries = {"P": (forge.paste_retype(jpg, total_box, new_total, q), ("total",))}
        item_name, item_amount = bill.items[int(rng.integers(0, len(bill.items)))]
        item_box = transform_box(next(f for f in bill.fields if f.name == item_name).box, matrix)
        forgeries["C"] = (forge.copy_move_digit(jpg, item_box, q, seed=b), (item_name,))
        if gemini is not None:
            cache = out / "gemini-cache"
            edited = forge.gemini_edit(gemini, jpg, total_box, new_total, q, cache)
            forgeries["G"] = (edited, ("total",))
            forgeries["G2"] = (whatsapp(edited)[0] if edited else None, ("total",))
            # G3: the total and one item change together, so the arithmetic still holds: only pixels can tell
            first = forge.gemini_edit(gemini, jpg, item_box, money(item_amount + delta), q, cache)
            both = forge.gemini_edit(gemini, first, total_box, new_total, q, cache) if first else None
            forgeries["G3"] = (both, ("total", item_name))
        for kind, (data, edited_fields) in forgeries.items():
            if data is None:
                discarded.append({"base": b, "kind": kind})
                continue
            g2 = kind == "G2"
            save(f"b{b}-{kind}", data, "jpg", {**base, "kind": kind,
                                               "fields": _fields(bill, matrix, whatsapp(jpg)[1] if g2 else 1.0,
                                                                 edited_fields)})
    (out / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "discarded.jsonl").write_text("".join(json.dumps(r) + "\n" for r in discarded))
    log.info("wrote %d images (%d forgeries discarded) to %s", len(rows), len(discarded), out)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    main(args.bases, args.seed, OUT, forge.GeminiImageEditor("social-pulse-510513"))
