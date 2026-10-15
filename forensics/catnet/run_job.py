"""CAT-Net over a folder of JPEGs (local or gs://): one float16 heatmap (.npy) per image, plus done.json.

python run_job.py --images gs://bucket/eval/forensics/r1/images --out gs://bucket/eval/forensics/r1/catnet
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # the vendored CAT-Net code: lib/, Splicing/, experiments/

from lib import models  # noqa: E402
from lib.config import config, update_config  # noqa: E402
from Splicing.data.AbstractDataset import AbstractDataset  # noqa: E402

WEIGHTS = HERE / "weights" / "CAT_full_v2.pth.tar"
TRANSPOSE = {2: [Image.FLIP_LEFT_RIGHT], 3: [Image.ROTATE_180], 4: [Image.FLIP_TOP_BOTTOM],
             5: [Image.FLIP_LEFT_RIGHT, Image.ROTATE_90], 6: [Image.ROTATE_270],
             7: [Image.FLIP_LEFT_RIGHT, Image.ROTATE_270], 8: [Image.ROTATE_90]}


class _One(AbstractDataset):
    def __init__(self):
        super().__init__(crop_size=None, grid_crop=True, blocks=("RGB", "DCTvol", "qtable"), DCT_channels=1)

    def get_tamp(self, index):
        raise NotImplementedError


def load_model(device: torch.device):
    update_config(config, argparse.Namespace(cfg=str(HERE / "experiments" / "CAT_full.yaml"), opts=[
        "TEST.MODEL_FILE", str(WEIGHTS), "TEST.FLIP_TEST", "False", "TEST.NUM_SAMPLES", "0"]))
    model = models.network_CAT.get_seg_model(config)
    # weights_only: the file comes from a community mirror, and a pickle can carry code; this loader only
    # accepts tensors and plain values, so anything else fails to load instead of running.
    # strict: every tensor must exist in CAT-Net with the right shape, so a wrong or altered file fails too.
    state = torch.load(str(WEIGHTS), map_location="cpu", weights_only=True)
    model.load_state_dict(state["state_dict"], strict=True)
    return model.to(device).eval()


def heatmap(model, path: Path, device: torch.device) -> np.ndarray:
    """P(edited) per pixel at the image's size, in display orientation (as the backend's load_image sees it)."""
    tensor, _, qtable = _One()._create_tensor(str(path), None)
    with torch.no_grad():
        logits = model(tensor[None].to(device), qtable[None].to(device))
        prob = F.softmax(logits, dim=1)[:, 1:2]
        prob = F.interpolate(prob, size=tensor.shape[1:], mode="bilinear", align_corners=False)[0, 0]
    img = Image.open(path)
    h, w = img.height, img.width
    heat = Image.fromarray(prob[:h, :w].float().cpu().numpy())
    for op in TRANSPOSE.get(img.getexif().get(0x0112, 1), []):
        heat = heat.transpose(op)
    return np.clip(np.asarray(heat), 0, 1).astype(np.float16)


class _Folder:
    """A local folder or a gs:// prefix, behind the same few calls."""

    def __init__(self, uri: str):
        self.uri = uri.rstrip("/")
        self.gcs = uri.startswith("gs://")
        if self.gcs:
            from google.cloud import storage

            bucket, self.prefix = self.uri.removeprefix("gs://").split("/", 1)
            self.bucket = storage.Client().bucket(bucket)

    def names(self) -> list[str]:
        if self.gcs:
            return sorted(b.name.rsplit("/", 1)[-1] for b in self.bucket.client.list_blobs(self.bucket, prefix=self.prefix + "/"))
        return sorted(p.name for p in Path(self.uri).iterdir() if p.is_file())

    def fetch(self, name: str, local: Path) -> Path:
        if not self.gcs:
            return Path(self.uri) / name
        self.bucket.blob(f"{self.prefix}/{name}").download_to_filename(str(local / name))
        return local / name

    def put(self, name: str, data: bytes) -> None:
        if self.gcs:
            self.bucket.blob(f"{self.prefix}/{name}").upload_from_string(data)
        else:
            Path(self.uri).mkdir(parents=True, exist_ok=True)
            (Path(self.uri) / name).write_bytes(data)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"cuda: {torch.cuda.is_available()} device: {device}", flush=True)
    model = load_model(device)
    src, dst = _Folder(args.images), _Folder(args.out)
    done = {"execution": os.environ.get("CLOUD_RUN_EXECUTION", "local"), "ok": [], "errors": {}, "na": []}
    with tempfile.TemporaryDirectory() as tmp:
        for name in src.names():
            if not name.lower().endswith((".jpg", ".jpeg")):
                done["na"].append(name)  # CAT-Net reads JPEG compression traces: nothing to read in a PNG
                continue
            started = time.time()
            try:
                heat = heatmap(model, src.fetch(name, Path(tmp)), device)
            except Exception as e:  # one bad image never stops the run
                done["errors"][name] = f"{type(e).__name__}: {e}"[:300]
                continue
            buf = __import__("io").BytesIO()
            np.save(buf, heat)
            dst.put(Path(name).stem + ".npy", buf.getvalue())
            dst.put(Path(name).stem + ".time", f"{time.time() - started:.3f}".encode())
            done["ok"].append(name)
            print(f"{name}: {time.time() - started:.2f}s", flush=True)
    dst.put("done.json", json.dumps(done).encode())  # last: its presence means the run finished


if __name__ == "__main__":
    main()
