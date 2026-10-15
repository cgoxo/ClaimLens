# CAT-Net job

CAT-Net reads JPEG compression traces to map image areas that look edited. In ClaimLens it runs **only in the
cloud**, as the Cloud Run Job `claimlens-forensics` (L4 GPU, asia-southeast1). See `LICENSES.md`.

**Build** (from the repo root). The build downloads the weights, builds the image, runs `test_run_job.py`
inside it on CPU, and pushes it:

    gcloud builds submit forensics/catnet --config forensics/catnet/cloudbuild.yaml --region asia-south1 \
      --substitutions _IMAGE=asia-south1-docker.pkg.dev/social-pulse-510513/claimlens/claimlens-forensics:<tag>,_WEIGHTS_SHA256=<sha>

**Run** over a folder of JPEGs in the bucket:

    gcloud run jobs execute claimlens-forensics --region asia-southeast1 \
      --args=--images,gs://<bucket>/<prefix>/images,--out,gs://<bucket>/<prefix>/catnet --wait

**Output.** For each JPEG: `<name>.npy`, a float16 map of P(edited) at the image's size in display
orientation, and `<name>.time`. Non-JPEGs are listed as `na`. `done.json` is written last.

## Changes to the vendored code

None so far. It runs as-is on the pinned stack:
- Python 3.11;
- PyTorch 2.4.1 (CUDA 12.1 build): newer versions refuse full checkpoints in `torch.load` by default;
- numpy 1.26.4: the code uses `np.int`, which numpy 1.24 removed.

The pretrained RGB and DCT backbone files are only for training. At inference they are skipped with a warning,
and the full checkpoint is loaded instead.
