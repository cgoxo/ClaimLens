import io
import json

import numpy as np
from PIL import Image, ImageDraw

from eval.forensics import forge
from eval.forensics.bills import render_bill
from eval.forensics.make_set import main as make_set
from eval.forensics.photo import to_photo, transform_box


def _arr(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype(np.int16)


def test_render_is_deterministic_and_fields_are_where_the_ink_is():
    a, b = render_bill(3), render_bill(3)
    assert a.png == b.png and [f.box for f in a.fields] == [f.box for f in b.fields]
    img = _arr(a.png)
    total = next(f for f in a.fields if f.name == "total")
    x0, y0, x1, y1 = map(int, total.box)
    assert (img[y0:y1, x0:x1].mean(axis=2) < 120).sum() > 50  # the total's ink is inside its box


def test_boxes_follow_the_photo():
    bill = render_bill(5)
    jpg, matrix, _ = to_photo(bill.png, seed=5)
    photo = _arr(jpg).mean(axis=2)
    for f in [f for f in bill.fields if f.kind == "amount"][:3]:
        x0, y0, x1, y1 = map(int, transform_box(f.box, matrix))
        inside = (photo[y0:y1, x0:x1] < 120).sum()
        around = (photo[max(0, y0 - 30):y1 + 30, max(0, x0 - 30):x1 + 30] < 120).sum()
        assert inside >= 0.9 * around - 5  # the field's ink sits inside the transformed box


def _photo_and_field(seed=7):
    bill = render_bill(seed)
    jpg, matrix, q = to_photo(bill.png, seed)
    total = next(f for f in bill.fields if f.name == "total")
    return jpg, transform_box(total.box, matrix), q, bill


def test_classic_forgeries_change_only_the_field():
    jpg, box, q, _ = _photo_and_field()
    for edited in (forge.paste_retype(jpg, box, "Rs 99,900", q), forge.copy_move_digit(jpg, box, q, seed=1)):
        assert edited is not None
        assert forge.edit_is_local(jpg, edited, box)
        x0, y0, x1, y1 = map(int, box)
        assert np.abs(_arr(edited)[y0:y1, x0:x1] - _arr(jpg)[y0:y1, x0:x1]).mean() > 3


class FakeGemini:
    """Stands in for the image model: repaints whatever sits inside the green box. Optionally spoils far pixels."""

    def __init__(self, spoil=False):
        self.calls, self.spoil = 0, spoil

    def edit(self, png: bytes, prompt: str) -> bytes | None:
        self.calls += 1
        img = Image.open(io.BytesIO(png)).convert("RGB")
        arr = np.asarray(img)
        green = np.where((arr[:, :, 1] > 180) & (arr[:, :, 0] < 90) & (arr[:, :, 2] < 90))
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = green[1].min(), green[0].min(), green[1].max(), green[0].max()
        d.rectangle((x0, y0, x1, y1), fill=(240, 238, 232))
        d.text((x0 + 10, y0 + 6), "Rs 99,900", fill=(30, 30, 36))
        if self.spoil:
            d.rectangle((0, 0, 40, 40), fill=(0, 0, 0))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()


def test_gemini_edit_pastes_back_only_the_field_and_is_cached(tmp_path):
    jpg, box, q, _ = _photo_and_field()
    fake = FakeGemini()
    edited = forge.gemini_edit(fake, jpg, box, "Rs 99,900", q, cache_dir=tmp_path)
    assert edited is not None and forge.edit_is_local(jpg, edited, box)
    again = forge.gemini_edit(fake, jpg, box, "Rs 99,900", q, cache_dir=tmp_path)
    assert again == edited and fake.calls == 1


def test_a_gemini_edit_that_changes_far_pixels_is_discarded(tmp_path, caplog):
    jpg, box, q, _ = _photo_and_field()
    assert forge.gemini_edit(FakeGemini(spoil=True), jpg, box, "Rs 99,900", q, cache_dir=tmp_path,
                             paste_back=False) is None
    assert "not local" in caplog.text


def test_manifest_has_controls_and_one_edited_field_per_forgery(tmp_path):
    make_set(n_bases=2, seed=7, out=tmp_path, gemini=FakeGemini())
    rows = [json.loads(l) for l in (tmp_path / "manifest.jsonl").read_text().splitlines()]
    kinds = {r["kind"] for r in rows}
    assert {"control", "G", "G2", "G3", "P", "C"} <= kinds
    controls = {r["control_type"] for r in rows if r["kind"] == "control"}
    assert {"original", "whatsapp", "screenshot", "second_photo", "crease_shadow"} <= controls
    for r in rows:
        edited = [f for f in r["fields"] if f["edited"]]
        assert len(edited) == (0 if r["kind"] == "control" else 2 if r["kind"] == "G3" else 1), r
        assert (tmp_path / r["image"]).is_file()
