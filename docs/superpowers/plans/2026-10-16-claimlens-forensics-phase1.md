# ClaimLens pixel forensics, Phase 1 (measure) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build every candidate pixel detector, a forged test set we own, and a harness that scores them. Produce the report that decides which detectors ship. **Phase 2 (pipeline, findings, UI, Cloud Run Job) is not in this plan.**

**Architecture:**
- A `claimlens/pipeline/forensics/` package holds the image loading, the `Detector` protocol, five classical detectors and the Gemini close-up detector. Phase 2 reuses all of it.
- CAT-Net lives in `forensics/catnet/` with its own pinned environment, and is run over the set by a CLI.
- `backend/eval/forensics/` generates the set (fictional bills turned into phone-like photos, controls and forgeries) and scores every detector at field level.

**Tech Stack:** Python 3.12, NumPy, OpenCV (`opencv-python-headless`), Pillow, PyMuPDF, rapidfuzz · Gemini `gemini-3.1-flash-image` (forgeries) and `gemini-2.5-flash` (close-up) on Vertex · CAT-Net (PyTorch, jpegio).

**Spec:** `docs/superpowers/specs/2026-10-16-claimlens-pixel-forensics-design.md`

## Global Constraints

- **Detector rule:** a detector **returns `None` ("no opinion")** whenever it doesn't apply or fails. It never returns an all-zero map to mean clean, and it never raises past `Detector.heatmap`.
- **Image size:** the long side is at most **4,096 px** after loading. Classical detectors stay under **1.5 GiB** peak for a 9,000 × 12,000 input.
- **Tiny images:** below **600 px** on the long side, every detector returns `None`.
- **Field score:** the 95th percentile of the heatmap inside the box, dilated by **4 px**.
- **Metrics:** the half split for threshold vs evaluation is seeded (seed 7). Keep rule: **field AUC ≥ 0.70 on G or G2, and the false-positive rate on every control type is ≤ 5%** at the threshold fixed on the other half.
- **Gemini models:**
  - forgeries use `gemini-3.1-flash-image` (location `global`);
  - the close-up check uses `gemini-2.5-flash`;
  - both are cached on disk by a content hash, so reruns cost nothing.
- **Data:**
  - the set goes in `backend/data/eval/forensics/` (gitignored);
  - only `docs/eval/forensics-<date>.md` and the generator and harness code are committed;
  - CAT-Net weights are never committed (sha256-pinned download script).
- **Licences:** CAT-Net code is Apache 2.0 and its weights are CC-BY 4.0; attribution goes in `forensics/catnet/LICENSES.md`, together with the licence of the HRNet backbone file.
- **Test baselines:** backend `.venv/bin/pytest -q` (192 passed) and frontend `npx vitest run` (98 passed) stay green. New tests are added under `backend/tests/forensics/`.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **EXIF-rotated photos:** heatmaps and boxes must use the same orientation, or every field score is measured in the wrong place. Pinned in Task 1.
2. **Manifest boxes vs edited pixels:** after the perspective warp, the recorded field box must contain the pixels that actually changed, or the metrics are meaningless. Pinned in Task 3.
3. **Controls leaking into thresholds:** thresholds come from the other half only, and the false-positive rate is reported **per control type**, not averaged. Pinned in Task 6.
4. **Gemini editing the wrong area or refusing:** an output where pixels outside the dilated field box changed beyond JPEG noise is discarded and logged, never scored as a forgery. Pinned in Task 3.
5. **Detectors that are "n/a" on PNGs:** they are counted as no opinion in the report, not as negatives that would flatter their false-positive rate. Pinned in Task 6.

---

### Task 1: Image loading and the detector interface

**Files:**
- Create: `backend/claimlens/pipeline/forensics/__init__.py`, `image.py`, `base.py`
- Modify: `backend/pyproject.toml` (add `opencv-python-headless>=4.10`, `numpy>=1.26`)
- Test: `backend/tests/forensics/test_image.py`

**Interfaces:**
- `ImageInfo` (dataclass):
  - `format: str` (`"jpeg"`, `"png"`, `"other"`)
  - `jpeg_quality: int | None` (estimated from the luminance quantisation table)
  - `qtables: list[np.ndarray] | None`
  - `oriented: bool`
  - `original_size: tuple[int, int]`
  - `size: tuple[int, int]`
  - `scale: float` (analysed px per original px)
- `load_image(data: bytes) -> tuple[np.ndarray | None, ImageInfo | None]`: returns RGB uint8 after EXIF transpose and downscale to 4,096. Returns `(None, None)` on undecodable data. CMYK and greyscale are converted to RGB.
- `Detector` (Protocol), with `name: str`, `applies(info: ImageInfo) -> bool` and `heatmap(img: np.ndarray, info: ImageInfo, words: list[Box]) -> np.ndarray | None`.
- `safe_heatmap(d: Detector, img, info, words) -> np.ndarray | None`: wraps a detector so it returns `None` when the image is tiny (< 600), when it doesn't apply, on an exception (logged), or on a shape mismatch.
- `Box = tuple[float, float, float, float]` in analysed-image pixels.
- `field_score(heatmap: np.ndarray, box: Box) -> float`

- [ ] **Step 1: Write failing tests:**
  - `test_jpeg_info`: a PIL-saved q 90 JPEG gives `format == "jpeg"` and `85 <= jpeg_quality <= 95`.
  - `test_png_info`: format `png`, and `qtables is None`.
  - `test_exif_orientation`: a 200×100 image with orientation 6 loads as 100×200 with `oriented=True`, and a red square drawn at a known corner before rotating lands at the rotated position.
  - `test_huge_downscaled_and_memory`: a 9,000×12,000 JPEG loads with its long side at 4,096 and `scale≈0.341`; the tracemalloc peak during load is under 1.5 GiB.
  - `test_cmyk_grey_progressive`: each loads as RGB.
  - `test_corrupt`: truncated JPEG bytes give `(None, None)`.
  - `test_safe_heatmap_tiny_and_raising`: a 400×300 image gives `None`; a detector that raises gives `None`; a detector returning the wrong shape gives `None`.
  - `test_field_score`: a heatmap of zeros with a 1.0 patch inside the box gives `1.0`; the same patch 10 px outside the box gives `0.0`.
- [ ] **Step 2:** `.venv/bin/pip install -q 'opencv-python-headless>=4.10'`, then `.venv/bin/pytest tests/forensics/test_image.py -q`. Expected: FAIL (import).
- [ ] **Step 3: Implement.** Use `PIL.ImageOps.exif_transpose`. Estimate quality by comparing the luminance table with the standard IJG tables scaled for q 1..100 (closest wins). Take `qtables` from `img.quantization`. Downscale with `Image.reduce`/`resize` before converting to NumPy, so memory stays bounded.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(forensics): image loading and detector interface`.

### Task 2: Classical detectors

**Files:**
- Create: `backend/claimlens/pipeline/forensics/{ela,noise,dq,copymove,chars}.py`
- Test: `backend/tests/forensics/test_classical.py`

**Interfaces:** each module exposes a `Detector` instance: `ELA`, `NOISE`, `DQ`, `COPYMOVE`, `CHARS`.
- **`ela`:**
  - Applies to JPEG only.
  - Re-save at the image's own estimated quality.
  - Heatmap = abs diff, per-channel max, smoothed (Gaussian σ 3), normalised by the page's 99th percentile.
- **`noise`:**
  - Applies always.
  - High-pass residual (image minus median blur 3) → local std in 16-px blocks.
  - Heatmap = |log(block std / page median std)|, clipped to [0, 1] after dividing by 2.
- **`dq`:**
  - Applies to JPEG with qtables.
  - Per 8×8 block DCT; for the first 6 AC frequencies, a periodicity-based double-quantisation probability.
  - Heatmap = per-block mean probability that the block is *not* double-compressed in step with the page majority.
- **`copymove`:**
  - Applies always.
  - ORB (2,000 keypoints) self-matching with distance > 20 px and Hamming < 30; clusters of ≥ 4 consistent matches give 1.0 around both source and target areas.
  - Also exposes `pairs(img) -> list[tuple[Box, Box]]`.
- **`chars`:**
  - Applies when `words` is non-empty.
  - **Features** for each word box: Laplacian variance (sharpness), median ink colour (Lab), stroke width (distance-transform median), and background colour (ring 3 px around the box).
  - **Style classes:** words are clustered by (box height, stroke width) using k-means with k ≤ 3 by silhouette.
  - **Score:** each *number* box gets its robust z-distance from the median of its own class, mapped to [0, 1] with `min(1, z/4)`, and painted into its box.

- [ ] **Step 1: Write failing tests.** Synthetic page: white canvas with 20 lines of rendered text, saved as JPEG q 90. Then:
  - `test_ela_flags_pasted_patch`: paste a q 60 JPEG patch into the region of one number, re-save at q 90; that box's `field_score` is greater than 0.5 and the median of other number boxes is below 0.2.
  - `test_noise_flags_smoothed_patch`: blur one number region (inpainting proxy); its field score exceeds the others' 95th percentile.
  - `test_dq_flags_single_compressed_patch`: the clean page saved twice (q 75 then q 90), with one region pasted from the uncompressed original before the second save; that region scores above the others.
  - `test_copymove_finds_copied_digit`: copy one digit's pixels onto another digit; `pairs` returns a pair whose boxes overlap both locations.
  - `test_chars_flags_retyped_number`: one number re-rendered in a different font and colour; it scores highest.
  - **`test_chars_bold_total_not_flagged`:** a genuine bold, larger TOTAL line scores < 0.5. This pins the style classes.
  - **`test_png_dq_ela_no_opinion`:** a PNG gives `None` from `safe_heatmap(DQ)` and `safe_heatmap(ELA)`.
  - **`test_low_quality_no_opinion`:** at q 40, DQ and ELA return `None` (`applies` is false when `jpeg_quality < 50`).
  - **`test_no_words`:** CHARS gives `None` when `words == []`.
  - **`test_blank_page`:** every detector on an all-white page returns `None` or a map whose max is < 0.2, and never raises.
- [ ] **Step 2:** `.venv/bin/pytest tests/forensics/test_classical.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement each detector to the description above.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass. The `pytest --durations=5` report shows no test slower than 5 s.
- [ ] **Step 5: Commit** `feat(forensics): classical detectors (ELA, noise, double quantisation, copy-move, characters)`.

### Task 3: Forged test set generator

**Files:**
- Create:
  - `backend/eval/__init__.py`, `backend/eval/forensics/__init__.py`
  - `backend/eval/forensics/make_set.py`, `bills.py`, `photo.py`, `forge.py`
- Test: `backend/tests/forensics/test_make_set.py`

**Interfaces:**
- **`bills.render_bill(seed: int) -> tuple[bytes, list[Field]]`:** a fictional one-page hospital bill PDF rendered to a 2,480×3,508 RGB PNG at 300 dpi.
  - `Field(name: str, kind: "amount"|"date"|"invoice"|"text", box: Box, value: str)` covers every number field and some text words.
  - Variants come from the seed: font family, a bold TOTAL, a stamp over an amount, a handwritten note, a highlighter mark.
- **`photo.to_photo(png: bytes, seed) -> tuple[bytes, Matrix3x3]`:**
  - perspective warp of ±4°, brightness and contrast jitter, Gaussian blur σ ≤ 0.8, sensor noise σ 2–4;
  - saved as JPEG q 85–95;
  - returns the homography so the boxes can be transformed.
- **Controls** in `photo.py`:
  - `whatsapp(jpg)`: q 70 and long side 1,600;
  - `screenshot(jpg)`: PNG;
  - `second_photo(png, seed)`;
  - `crease_shadow(jpg, seed)`.
- **Forgeries** in `forge.py`, each `(photo_jpg, field, seed) -> bytes | None`:
  - **`paste_retype`**;
  - **`copy_move_digit`**;
  - **`gemini_edit(client, cache_dir)`:** a crop with 50% context (minimum 150 px), a mask drawn as a 3-px green rectangle, a 2× upscale, a templated prompt (*"Change only the number inside the green box to {new}, matching the font, colour and paper exactly; remove the green box"*), then paste back **only the field box** and save as JPEG at the photo's quality;
  - **`gemini_edit_fixed_math`:** edits the total and one line item consistently;
  - **`shared(jpg)`:** WhatsApp after any forgery.
- **Validation `edit_is_local(before, after, box) -> bool`:** the pixel difference outside the box (dilated 8 px) has a 99th percentile under 12. If it fails, the forgery is discarded and logged.
- **`make_set.main(n_bases=40, seed=7, out=Path)`** writes `manifest.jsonl` rows: `{id, base, kind: control|G|G2|G3|P|C, control_type?, image, fields: [{name, kind, box, edited}]}`.

- [ ] **Step 1: Write failing tests,** with Gemini faked by a function that repaints the box with a slightly different number:
  - `test_render_is_deterministic`: the same seed gives byte-identical PNGs.
  - `test_boxes_follow_the_photo`: after `to_photo`, each transformed field box still contains ≥ 90% of that field's dark pixels (checked by rendering the field alone).
  - `test_forgery_changes_only_the_field`: for each forgery kind, `edit_is_local` is true and the field's pixels changed (mean abs diff > 10).
  - `test_bad_gemini_edit_discarded`: a fake that also changes a far area is dropped and logged.
  - `test_manifest_rows`: a 2-base run writes rows for all controls and forgeries with exactly one `edited: true` field per forgery (two for G3).
  - `test_gemini_cache`: the second run makes no fake calls.
- [ ] **Step 2:** `.venv/bin/pytest tests/forensics/test_make_set.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `gemini_edit` uses `google.genai` with `response_modalities=["IMAGE"]`, model `gemini-3.1-flash-image`, location `global`. Network failures and refusals return `None` (logged).
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(eval): forged bill test set generator`.

### Task 4: Gemini close-up detector

**Files:**
- Create: `backend/claimlens/pipeline/forensics/gemini_closeup.py`
- Test: `backend/tests/forensics/test_gemini_closeup.py`

**Interfaces:**
- `GeminiCloseup(client, model="gemini-2.5-flash", cache_dir=None)` is a `Detector`. It applies when `words` holds number boxes.
- For each number box (at most 30 per page):
  - crop the box with 2× context, at most 512 px;
  - ask for JSON `{"looks_edited": bool, "confidence": 0..1, "why": str}`;
  - score = `confidence if looks_edited else 1 - confidence`, mapped so that 0.5 = unsure, and painted into the box.
- A refusal, error or invalid JSON leaves that box at 0.5 ("no opinion" at the field level). Every box at 0.5 makes the result `None`.

- [ ] **Step 1: Write failing tests** with a fake client:
  - **Score mapping:** a clear "edited" answer gives a box score near 1, and a clear "genuine" answer near 0.
  - **Bad answers:** a refusal and invalid JSON both give 0.5 for that box.
  - **All unsure:** every box failing gives `None`.
  - **Box cap:** only 30 boxes are asked.
  - **Cache:** the second identical call hits the cache.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(forensics): Gemini close-up detector (to be measured)`.

### Task 5: CAT-Net runner (for measurement)

**Files:**
- Create:
  - `forensics/catnet/README.md`, `LICENSES.md`, `requirements.txt` (pinned)
  - `forensics/catnet/get_weights.sh` (downloads with sha256 check)
  - `forensics/catnet/run_dir.py`
  - `forensics/catnet/Dockerfile` (fallback)
- Test: `forensics/catnet/test_smoke.py` (run in the CAT-Net environment, not the backend suite)

**Interfaces:**
- **Code:** the upstream CAT-Net repository is vendored into `forensics/catnet/vendor/` at a pinned commit, keeping its LICENSE files.
- **`run_dir.py --images <dir> --out <dir>`:** for each JPEG it writes `<name>.npy` (a float16 heatmap at the original size, EXIF-transposed to match `load_image`) and `timings.jsonl`. Non-JPEGs are skipped with `"n/a"`.
- **Environment:** `python3.12 -m venv forensics/catnet/.venv`, with requirements pinned to the newest PyTorch the code runs on.
  - If `jpegio` or the code can't run natively on arm64 macOS, **stop and ask the user** to start Docker Desktop (`docker run --platform linux/amd64`).
  - No cloud resources are created in this phase.

- [ ] **Step 1: Write the smoke test:** on one genuine sample JPEG and one with a q 60 patch pasted in, the heatmap shape equals the image size, and the patch area's mean is above the rest's 95th percentile.
- [ ] **Step 2:** `get_weights.sh`, then `forensics/catnet/.venv/bin/python -m pytest forensics/catnet/test_smoke.py -q`. Expected: FAIL before `run_dir.py` exists.
- [ ] **Step 3:** Implement `run_dir.py`. Record any code changes needed for the current PyTorch in `README.md`.
- [ ] **Step 4:** Rerun the smoke test. Expected: PASS.
- [ ] **Step 5: Commit** `feat(forensics): CAT-Net runner for measurement` (vendor code and scripts only, no weights).

### Task 6: Harness, run, report

**Files:**
- Create: `backend/eval/forensics/score.py`, `backend/eval/forensics/report.py`
- Test: `backend/tests/forensics/test_score.py`
- Output: `docs/eval/forensics-2026-10-16.md` (committed), `backend/data/eval/forensics/results.jsonl` (not committed)

**Interfaces:**
- **`score.py`:** runs every detector (classical via `safe_heatmap`, `GeminiCloseup`, CAT-Net heatmaps loaded from `.npy` and scaled to the analysed size) on each manifest image. It writes `results.jsonl` rows `{image, kind, control_type, field, edited, detector, score|null, seconds}`.
- **`metrics(rows, detector, kinds) -> {auc, tpr_at_5fpr, threshold, fpr_by_control: dict, n_no_opinion}`:**
  - rows are split by base with seed 7;
  - the threshold is fixed on half A and the metrics are reported on half B;
  - `null` scores are excluded and counted.
- **`fused(rows, detectors)`:** the max and the mean of the given detectors' field scores.
- **`report.py`** writes the markdown report:
  - one table per detector per forgery kind;
  - a false-positive table per control type;
  - timing, and ₹/case at the catalogue rates ($0.0000216 vCPU-s, $0.0000024 GiB-s for asia-southeast1; asia-south1 $0.000018 / $0.000002; L4 $0.00022404/s), at ₹84/$;
  - **the keep-rule verdict per detector**;
  - the stated known limits.

- [ ] **Step 1: Write failing tests** with hand-made rows:
  - **Perfect separation:** gives AUC 1.0.
  - **Shuffled scores:** gives about 0.5 (within ±0.1 over 2,000 rows).
  - **Thresholds use half A only:** changing half-B scores doesn't move the threshold.
  - **False positives are per control type:** a detector that fires on every `bold_total` control but nothing else shows `fpr_by_control["bold_total"] == 1.0` and fails the keep rule.
  - **No opinion isn't a negative:** `null` rows are counted in `n_no_opinion` and excluded from the AUC.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Run it.**
  - `python -m eval.forensics.make_set --bases 40` (≈ $8 of Gemini image edits; the set is cached).
  - The CAT-Net run over the set's JPEGs.
  - `python -m eval.forensics.score`, then `python -m eval.forensics.report`.
- [ ] **Step 6: Commit** the report as `docs: forensics phase 1 measurement report`. **Stop here and share the numbers with the user** before any Phase 2 plan.
