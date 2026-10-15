"""Run CAT-Net over the test set's JPEGs on the cloud GPU job, and fetch its heatmaps.

python -m eval.forensics.catnet_remote --run r1
"""

import argparse
import json
import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)
SET = Path(__file__).resolve().parents[2] / "data" / "eval" / "forensics"
PROJECT, REGION, JOB, BUCKET = "social-pulse-510513", "asia-southeast1", "claimlens-forensics", "social-pulse-510513-claimlens"


def _gcloud(args: list[str]) -> tuple[int, str, str]:
    done = subprocess.run(["gcloud", *args], capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


class GcsStore:
    def __init__(self):
        from google.cloud import storage

        self.client = storage.Client(project=PROJECT)

    def _blob(self, uri: str):
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        return self.client.bucket(bucket).blob(name)

    def exists(self, uri: str) -> bool:
        return self._blob(uri).exists()

    def upload(self, local: Path, uri: str) -> None:
        self._blob(uri).upload_from_filename(str(local))

    def read_text(self, uri: str) -> str:
        return self._blob(uri).download_as_text()

    def download_prefix(self, prefix: str, local_dir: Path) -> Path:
        bucket, name = prefix.removeprefix("gs://").split("/", 1)
        local_dir.mkdir(parents=True, exist_ok=True)
        for blob in self.client.list_blobs(bucket, prefix=name):
            if blob.name.endswith(".npy"):
                blob.download_to_filename(str(local_dir / blob.name.rsplit("/", 1)[-1]))
        return local_dir


def run(manifest: Path, bucket: str, run_id: str, gcloud=_gcloud, store=None, local: Path | None = None) -> Path:
    """Upload the JPEGs (skipping ones already there), run the job and wait, check it's this run's output,
    and download the heatmaps. Returns the local folder of .npy files."""
    store = store or GcsStore()
    root = manifest.parent
    prefix = f"gs://{bucket}/eval/forensics/{run_id}"
    for row in (json.loads(l) for l in manifest.read_text().splitlines() if l.strip()):
        if not row["image"].lower().endswith((".jpg", ".jpeg")):
            continue
        uri = f"{prefix}/images/{Path(row['image']).name}"
        if not store.exists(uri):
            store.upload(root / row["image"], uri)
    code, out, err = gcloud(["run", "jobs", "execute", JOB, f"--region={REGION}", f"--project={PROJECT}",
                             f"--args=--images,{prefix}/images,--out,{prefix}/catnet", "--wait",
                             "--format=value(metadata.name)"])
    if code != 0:
        link = re.search(r"https://console\.cloud\.google\.com\S+", err)
        raise RuntimeError(f"CAT-Net job failed: {link.group(0) if link else err.strip()[:300]}")
    execution = out.strip().splitlines()[-1] if out.strip() else ""
    done = json.loads(store.read_text(f"{prefix}/catnet/done.json"))
    if done.get("execution") != execution:
        raise RuntimeError(f"done.json is from another execution ({done.get('execution')}, expected {execution})")
    if done.get("errors"):
        log.warning("CAT-Net could not read %d images: %s", len(done["errors"]), list(done["errors"])[:5])
    return store.download_prefix(f"{prefix}/catnet/", local or root / "catnet")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(run(SET / "manifest.jsonl", BUCKET, args.run))
