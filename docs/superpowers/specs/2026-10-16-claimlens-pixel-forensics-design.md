# ClaimLens pixel forensics: design

Date: 2026-10-16 · Status: approved in chat, awaiting written-spec review

Sub-project **C** of five (A quick wins: live · B two forms, job queue, document check: live · **C pixel forensics** · D chat · E evaluation).

## 1. Goal and success criteria

**Goal.** Flag numbers on **photographed or scanned** claim pages whose pixels look edited, including AI inpainting, the attack from AIForge-Doc (arXiv 2602.20569). Each flag is a finding with a marker on the exact number. The flag is never proof on its own: it becomes strong evidence only when the text cross-checks also disagree.

**Done when:**
1. The **measurement harness** (§3) scores every detector on our own forged test set, and the report is committed.
2. Only detectors that pass the **keep rule** (§3.4) are switched on.
3. With forensics on, the pipeline produces the findings in §5 and shows a heatmap layer in the viewer.
4. **The full edge-case matrix in §8 passes.**
5. **Prod check:** a Gemini-edited photo of the sample bill is flagged on the edited number, and the untouched photo is not.
6. **Rollout:** `FORENSICS=off` is the default until step 2 is done. Turning it on is a settings change only.

**Out of scope:**
- Watermark and provenance metadata (C2PA, IPTC, SynthID): parked in the backlog by the user.
- Training or fine-tuning models.
- Video.
- Forensics on digital PDF pages, which are already covered by the font, hidden-text and metadata checks.

## 2. Pieces and where they run

| Piece | Kind | Runs in | Cost per case (est.) |
| --- | --- | --- | --- |
| `ela`: error level analysis | Classical | `claimlens-api`, a pipeline step | ≈ ₹0.01 |
| `noise`: local noise inconsistency | Classical | `claimlens-api` | ≈ ₹0.01 |
| `dq`: JPEG double-quantisation map | Classical | `claimlens-api` | ≈ ₹0.01 |
| `copymove`: duplicated regions (ORB keypoints) | Classical | `claimlens-api` | ≈ ₹0.01 |
| `chars`: character consistency (sharpness, ink colour, stroke width and background of each number against the other text on the page, using OCR word boxes) | Classical, document-specific | `claimlens-api` | ≈ ₹0.01 |
| `catnet`: CAT-Net v2 (Apache 2.0 code, CC-BY 4.0 weights, attribution in About and README) | AI model | **Cloud Run Job `claimlens-forensics`**: CPU, 4 vCPU and 8 GiB, **asia-south1**. A GPU (L4, asia-southeast1) is a one-setting change | ≈ ₹0.45 on CPU / ≈ ₹0.9 on GPU |
| `gemini_closeup`: a crop of each number sent to Gemini 2.5 Flash, asking "does this look different from its surroundings?" | AI model | Gemini API | ≈ ₹0.3 |

**Interface.** Every detector implements:

```
class Detector(Protocol):
    name: str
    def applies(self, page: PageInfo, image: ImageInfo) -> bool      # e.g. dq/ela/catnet need a JPEG
    def heatmap(self, image: np.ndarray, image_info: ImageInfo, page: PageInfo) -> np.ndarray | None  # HxW in [0,1]
```

**`ImageInfo`** records:
- the format;
- the JPEG quality estimate and quantisation tables, when present;
- whether EXIF orientation was applied;
- the original size, and the size actually analysed. Images are scaled to at most 4,096 px on the long side, so memory stays bounded.

**Rules:**
- A detector that doesn't apply, errors or times out returns **None, meaning "no opinion"**, never "clean".
- The classical detectors live in `claimlens/pipeline/forensics/`.
- CAT-Net lives in `forensics/catnet/` (its own Dockerfile and pinned PyTorch), with the weights copied into the image at build time and never downloaded at runtime.

## 3. Phase 1: measure before building

### 3.1 Forged test set (`backend/eval/forensics/make_set.py`)

All data is generated from our fictional samples, so we own it. It goes in `backend/data/eval/forensics/` (gitignored), and a manifest records the ground truth: the box of each edited field.

**Bases:** 40 fictional bills rendered with random names, amounts, dates and invoice numbers (`make_example.py` with a seed). Each is turned into a **phone-like photo**:
- perspective warp of ±4°;
- brightness and contrast jitter;
- mild blur;
- sensor-like noise;
- saved as JPEG at q 85–95.

**Genuine controls,** with nothing edited:
- the original photo;
- re-saved at q 70 (WhatsApp-like) and resized to 1,600 px;
- a screenshot (PNG);
- a second photo of the same bill;
- a **bold total line** (a legitimately different font);
- a rubber stamp and a handwritten note;
- a highlighter mark;
- a crease and a shadow.

**Forgeries,** each changing exactly one field (total, a line amount, the date, or the invoice number), with the box recorded:
- **G.** Gemini image editing (`gemini-2.5-flash-image`), the paper's method: crop with context, mask and prompt, then paste back only the field box.
- **P.** Classic paste: draw a rectangle in the paper colour and retype the value in a similar font.
- **C.** Copy-move: copy a digit from elsewhere on the same bill over a digit of the field.
- **G2.** Like G, then saved at q 70 (to simulate sharing).
- **G3.** Like G, but the arithmetic is also fixed (total and item changed together), so **only pixels** can catch it.

**Size:** about 40 bases × (6 controls + 5 forgeries) ≈ 440 images. Generating the Gemini edits costs about $8. The script is deterministic for a given seed and caches Gemini outputs.

### 3.2 Harness (`backend/eval/forensics/score.py`)

For every image and detector:
- **Field level** (the unit that matters):
  - each **number box**, from OCR, gets the detector's score = the 95th percentile of the heatmap inside the box (dilated by 4 px);
  - positives are the edited boxes, negatives are every other number box on forged images and every number box on controls.
- **Image level:** the maximum field score.
- **Time:** wall-clock per image.

### 3.3 Report (`docs/eval/forensics-<date>.md`)

Per detector and per forgery type (G, P, C, G2, G3):
- field AUC;
- **true-positive rate at 5% false-positive rate** on genuine number boxes;
- the false-positive rate on each control type, listed separately: bold totals, stamps, WhatsApp re-save, screenshots;
- median and p95 time.

The report also covers **fused** scores: the maximum, and the mean of the kept detectors.

### 3.4 Keep rule

A detector is switched on only if, on the held-out half of the set:
- **field AUC ≥ 0.70** on G or G2, **and**
- **the false-positive rate on every control type is ≤ 5%** at the chosen threshold.

Thresholds are fixed from the other half. `gemini_closeup` and `catnet` must pass this rule like any other detector. If `catnet` fails, the Cloud Run Job (§6) is not built.

## 4. Phase 2: pipeline step

**Placement.** A new step, `forensics(ctx)`, runs after Read and the document check, **in parallel with Extract**: a thread for the classical detectors, and the CAT-Net Job started at the same time. Its results are joined before the checks run.

**Which pages:** only claim-stream pages of kind `image`, `scanned` or `scanned_with_text`, and only when `FORENSICS != "off"`.

**Results:**
- per page, a fused heatmap saved as `cases/{id}/heatmaps/claim/{page}.png`;
- per number box (OCR spans that match `MONEY_RE`, a date or an invoice key), `{detectors: {name: score}, fused: score}`.

**Fail-open.** If a detector or the Job fails or times out (`FORENSICS_TIMEOUT`, 300 s), the case still finishes, with a **low** note `pixel_check_incomplete` that names what didn't run. A case never fails because of forensics.

## 5. Findings (decided by code)

| Code | Severity | When | Cites |
| --- | --- | --- | --- |
| `edited_number` | **medium** | A number box's fused score is ≥ the threshold | The number's box, with `source="page"`. Detail names each detector that agreed |
| `edited_number` (escalated) | **critical** | As above, **and** the same number is cited by `sum_mismatch`, `claimed_amount_mismatch`, `date_order` or `inpatient_outside_stay` | Both citations. The text-based finding stays as it is |
| `pixel_check_incomplete` | low | §4 fail-open | The page (`source="metadata"`) |

**Rules:**
- **Stamps, logos and handwriting:** only number boxes become findings. A hot region with no number in it is shown on the heatmap only.
- **Title:** `"Rs 48,500 on claim page 3 looks edited"`.
- **Detail:** `"Compression mismatch (CAT-Net) and noise inconsistency around this number. A person should look closely."`, plus the escalation text when it applies.
- **Score:** weights are unchanged (medium 10, critical 40), with no double counting. When escalated, the `edited_number` finding replaces the medium one.

## 6. CAT-Net as a Cloud Run Job

**Container.** `forensics/catnet/Dockerfile`, with Python and PyTorch pinned for the original code, plus `jpegio`. The weights `CAT_full_v2.pth.tar` and the HRNet ImageNet weights are copied in at build time, after their licences are recorded in `forensics/catnet/LICENSES.md`.

**Run.**
- **Command:** `python run.py --case <id> --pages <list>`.
- **Input:** the **original uploaded JPEG**, read from GCS. The page PNG would have no JPEG traces, so CAT-Net has nothing to work with in it.
- **Output:** `cases/{id}/catnet/{page}.npy` (the heatmap) and `done.json`, which lists each page as either ok or an error.

**Trigger.**
- The pipeline calls the Cloud Run Admin API `jobs.run` with argument overrides, then **polls the execution** until it succeeds, fails or hits the timeout.
- Each execution is one task for one case. At most 4 executions run at once: the job queue's `max_concurrent_dispatches` (10) bounds cases, and the pipeline holds a semaphore of 4 around `jobs.run`.

**Terraform:**
- **The job itself:** `google_cloud_run_v2_job.forensics`, in asia-south1, with 4 vCPU, 8 GiB, a 600 s task timeout and 0 retries (the pipeline handles failure).
- **The job's account, `claimlens-forensics`:** `storage.objectViewer` on the bucket prefix `cases/`, plus `objectCreator` for its outputs.
- **The API's account, `claimlens-api`:** permission to run the job with overrides (`run.jobs.runWithOverrides` and `run.executions.get`), granted on **this job only** through a custom role.

**Settings:** `FORENSICS = off | classical | full` (full adds CAT-Net and, if kept, `gemini_closeup`), `FORENSICS_JOB`, `FORENSICS_REGION`, `FORENSICS_TIMEOUT`.

## 7. Frontend

**Viewer.** A **"Pixel heatmap"** toggle, off by default, overlays `heatmaps/claim/{page}.png` at 40% opacity. It's shown only on pages that have a heatmap.

**Findings.**
- `edited_number` uses the normal marker on the number's box.
- The finding card lists the agreeing detectors as small tags: "compression", "noise", "characters", "copy-move", "CAT-Net", "Gemini close-up".

**API.** `GET /api/cases/{id}/heatmaps/{doc}/{page}.png`. It is owner-checked like page images, and returns 404 when there is no heatmap.

## 8. Testing beyond the happy path

Every row is a pytest test unless it is marked *eval* (scored by the harness) or *browser* (a manual check in §1).

### 8.1 Inputs the detectors must survive (never crash; give no opinion where they can't judge)

| Case | Expected |
| --- | --- |
| Digital PDF page | Forensics skipped. No `edited_number`. The existing tamper checks are unchanged |
| PNG photo (no JPEG tables) | `dq`, `ela` and `catnet` give no opinion; `noise`, `chars` and `copymove` still run. The report shows "n/a", not "clean" |
| Scanned PDF page (image inside a PDF) | The embedded image is extracted. If it's a JPEG (DCTDecode), its bytes go to `dq`/`catnet`; otherwise it's treated as a PNG |
| Tiny image (< 600 px on the long side) | Every detector gives no opinion. The low note says the image is too small to check |
| Huge image (e.g. 9,000 × 12,000) | Downscaled to 4,096 px for the classical detectors. Memory stays under 1.5 GiB (asserted with tracemalloc). CAT-Net gets the original bytes, and the Job tiles them |
| EXIF orientation 6 or 8 (rotated phone photo) | Heatmaps line up with the displayed page and the OCR boxes: a test checks a known edited box lands on the same pixels |
| Greyscale JPEG, CMYK JPEG, progressive JPEG | Run, or give no opinion; never raise |
| Truncated or corrupt JPEG (the upload validator lets it through as an image) | No opinion, plus a `pixel_check_incomplete` note. The case still finishes READY |
| Very low quality (q < 50) | `dq`/`ela` give no opinion (no usable signal), recorded in the report |
| Page with no OCR words | No number boxes, so no `edited_number`. The heatmap is still saved |

### 8.2 Genuine documents that look "different" (false positives)

| Case | Expected |
| --- | --- |
| Bold or larger TOTAL line | Not flagged. `chars` compares each number with numbers **of the same style class** (clustered by stroke width and height), not with all text. *eval* row + unit test on the bold-total control |
| Rubber stamp or signature over an amount | Not flagged above threshold. *eval*: the false-positive rate on the stamp control is ≤ 5% |
| Highlighter, crease, shadow, glare | Not flagged. *eval* controls |
| Re-saved at q 70 or resized (WhatsApp) | Not flagged: double compression of the **whole** image is uniform. *eval* control |
| Screenshot of a genuine photo | Not flagged. *eval* control |
| Two genuine photos of the same page | `copymove` doesn't treat the two images as one. It works **within a single page only**. Duplicate pages remain the job of `duplicate_page_image` |
| A handwritten amount on a printed bill | Not `edited_number` on its own. It may surface as low on the heatmap only |

### 8.3 Forgeries: what should be caught, and the known limits

| Case | Expected |
| --- | --- |
| G: Gemini edit of the total | *eval*: the field true-positive rate at 5% false positives is reported. If kept, the end-to-end test produces `edited_number` on that box |
| G3: arithmetic fixed too | `edited_number` (medium) with no text finding. This is the case only pixels can catch |
| Total edited **and** items don't add up | Escalated to **critical**, with both citations. One finding only, not medium plus critical |
| P: classic paste/retype | Caught mostly by `chars`/`ela`. *eval* |
| C: copy-move digit | `copymove` links the source and target boxes, and the detail names both |
| G2: Gemini edit, then shared at q 70 | *eval*. The weaker signal is documented in the report |
| **Known limit:** the whole page AI-generated, or the edit re-photographed from a screen | No local anomaly is expected. Documented in the report and the README as a limit, not hidden |
| **Known limit:** PNG edits | Weaker signal (no JPEG traces). Documented |

### 8.4 System failures (fail-open, never a failed case)

| Case | Expected |
| --- | --- |
| CAT-Net Job fails to start (quota, permission) | `pixel_check_incomplete` (low) naming CAT-Net. The classical detectors' findings are still kept. Case READY |
| Job times out (> `FORENSICS_TIMEOUT`) | As above. The pipeline stops polling, and a later finish of the Job is ignored, because results are keyed by the run's execution name |
| `done.json` missing, or reports an error for one page | That page has no CAT-Net opinion. Other pages are used |
| Heatmap shape doesn't match the page | Resized with a recorded warning. If the aspect ratio differs by more than 2%, it's dropped (no opinion) |
| `gemini_closeup` refuses, errors or hits a rate limit | No opinion for that number. The case continues |
| Two cases run at once | Each Job execution writes under its own case prefix. A test runs two fake Jobs concurrently and checks no output is mixed up |
| A delivery retried after a crash (run-once guard) | The Job is started again for the new attempt, and stale outputs from the earlier attempt are ignored (execution name in `done.json`) |
| `FORENSICS=off` | Findings are byte-identical to today's for the sample (regression test) |
| An old case from before C | Opens with no heatmap toggle. The heatmap API returns 404 |

### 8.5 Security and cost

| Case | Expected |
| --- | --- |
| Heatmap URL for someone else's case | 404 (owner check), the same as page images |
| The API account starting any job other than `claimlens-forensics` | Denied by IAM (role scoped to the job). Checked once in the prod check |
| A case with 80 image pages | Forensics capped at `FORENSICS_MAX_PAGES` (40). The note names the pages that weren't checked |
| Cost per case | The harness records time. The report estimates ₹/case from the measured median at the billing-catalogue rates |

## 9. Rollout

1. Phase 1: build the set, harness and report. **Stop and share the numbers** before Phase 2.
2. Phase 2: build only the detectors that were kept, deployed with `FORENSICS=off`.
3. Turn on `classical`, then `full`, in prod after the §1 prod check.
