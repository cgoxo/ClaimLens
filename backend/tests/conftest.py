from pathlib import Path

import pytest

from claimlens.settings import Settings

BACKEND = Path(__file__).resolve().parent.parent
SAMPLES = BACKEND / "samples"
FAKE_AI = Path(__file__).resolve().parent / "fixtures" / "ai" / "sample"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # isolate from any developer .env / shell vars
    for var in ("STORAGE", "DB", "AI", "OCR", "AUTH_MODE", "APP_ENV", "BUCKET"):
        monkeypatch.delenv(var, raising=False)
    return Settings(_env_file=None, data_dir=tmp_path, ai="fake", fake_ai_dir=FAKE_AI, jobs="inline")


def make_ctx(tmp_path, ai=None, claim="claim.pdf", policy="policy.pdf"):
    """Read the sample PDFs into a Ctx (no extract yet)."""
    from claimlens.ai import FakeAi
    from claimlens.db import LocalDb
    from claimlens.deps import Deps
    from claimlens.ocr import NoOcr
    from claimlens.pipeline.context import Ctx
    from claimlens.pipeline.read import ReadResult, read_document
    from claimlens.storage import LocalStorage

    storage = LocalStorage(tmp_path / "files")
    deps = Deps(settings=Settings(_env_file=None, data_dir=tmp_path, ai="fake"),
                storage=storage, db=LocalDb(tmp_path / "db"), ai=ai or FakeAi(FAKE_AI), ocr=NoOcr())
    read, files = ReadResult(), {}
    for doc, name in (("claim", claim), ("policy", policy)):
        data = (SAMPLES / name).read_bytes()
        key = f"cases/c1/{doc}.pdf"
        storage.put(key, data, "application/pdf")
        files[doc] = key
        read.extend(read_document(doc, data, name, "c1", storage, NoOcr()))
    return Ctx(case_id="c1", read=read, deps=deps, files=files)


@pytest.fixture
def ctx(tmp_path):
    from claimlens.pipeline.extract import extract

    c = make_ctx(tmp_path)
    extract(c)
    return c
