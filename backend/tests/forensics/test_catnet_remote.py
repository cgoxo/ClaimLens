import json

import pytest

from eval.forensics import catnet_remote


class FakeStore:
    def __init__(self, existing=(), files=None):
        self.objects = set(existing)
        self.files = files or {}
        self.uploaded = []

    def exists(self, uri):
        return uri in self.objects

    def upload(self, local, uri):
        self.uploaded.append(uri)
        self.objects.add(uri)

    def read_text(self, uri):
        return self.files[uri]

    def download_prefix(self, prefix, local_dir):
        local_dir.mkdir(parents=True, exist_ok=True)
        for uri, data in self.files.items():
            if uri.startswith(prefix) and uri.endswith(".npy"):
                (local_dir / uri.rsplit("/", 1)[-1]).write_bytes(data)
        return local_dir


def _manifest(tmp_path):
    (tmp_path / "images").mkdir()
    rows = []
    for name, ext in (("a", "jpg"), ("b", "jpg"), ("c", "png")):
        (tmp_path / "images" / f"{name}.{ext}").write_bytes(b"x")
        rows.append({"id": name, "image": f"images/{name}.{ext}"})
    (tmp_path / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "manifest.jsonl"


def _gcloud(execution="ex-1", code=0, stderr=""):
    calls = []

    def run(args):
        calls.append(args)
        return code, execution + "\n", stderr

    run.calls = calls
    return run


PREFIX = "gs://bkt/eval/forensics/r1"


def test_uploads_only_jpegs_and_skips_what_is_already_there(tmp_path):
    store = FakeStore(existing={f"{PREFIX}/images/a.jpg"},
                      files={f"{PREFIX}/catnet/done.json": json.dumps({"execution": "ex-1", "ok": ["b.jpg"]}),
                             f"{PREFIX}/catnet/b.npy": b"npy"})
    gcloud = _gcloud()
    out = catnet_remote.run(_manifest(tmp_path), "bkt", "r1", gcloud=gcloud, store=store, local=tmp_path / "out")
    assert store.uploaded == [f"{PREFIX}/images/b.jpg"]  # a.jpg was there; c.png isn't a JPEG
    assert (out / "b.npy").read_bytes() == b"npy"
    args = gcloud.calls[0]
    assert args[:4] == ["run", "jobs", "execute", "claimlens-forensics"]
    assert f"--args=--images,{PREFIX}/images,--out,{PREFIX}/catnet" in args and "--wait" in args


def test_results_from_another_execution_are_refused(tmp_path):
    store = FakeStore(files={f"{PREFIX}/catnet/done.json": json.dumps({"execution": "ex-OLD", "ok": []})})
    with pytest.raises(RuntimeError, match="another execution"):
        catnet_remote.run(_manifest(tmp_path), "bkt", "r1", gcloud=_gcloud("ex-1"), store=store, local=tmp_path / "o")


def test_a_failed_execution_raises_with_the_log_link(tmp_path):
    gcloud = _gcloud(code=1, stderr="ERROR: execution failed. https://console.cloud.google.com/run/jobs/x/logs")
    with pytest.raises(RuntimeError, match="https://console.cloud.google.com/run/jobs/x/logs"):
        catnet_remote.run(_manifest(tmp_path), "bkt", "r1", gcloud=gcloud, store=FakeStore(), local=tmp_path / "o")
