from dataclasses import dataclass
from typing import Any

from claimlens.settings import Settings


@dataclass
class Deps:
    settings: Settings
    storage: Any
    db: Any
    ai: Any
    ocr: Any
    jobs: Any = None
    chat_ai: Any = None


def build_deps(settings: Settings) -> Deps:
    """Pick each implementation from settings. GCP libraries load only when chosen."""
    if settings.storage == "gcs":
        from claimlens.storage import GcsStorage

        storage = GcsStorage(settings.bucket)
    else:
        from claimlens.storage import LocalStorage

        storage = LocalStorage(settings.data_dir / "files")

    if settings.db == "firestore":
        from claimlens.db import FirestoreDb

        db = FirestoreDb(settings.gcp_project, settings.firestore_db)
    else:
        from claimlens.db import LocalDb

        db = LocalDb(settings.data_dir / "db")

    if settings.ai == "fake":
        from claimlens.ai import FakeAi
        from claimlens.chat.model import FakeChat

        ai = FakeAi(settings.fake_ai_dir)
        chat_ai = FakeChat([])
    else:
        from claimlens.ai import VertexGemini
        from claimlens.chat.model import VertexChat

        ai = VertexGemini(settings.gcp_project, settings.vertex_location, settings.gemini_model)
        chat_ai = VertexChat(settings.gcp_project, settings.vertex_location, settings.gemini_model)

    if settings.ocr == "docai":
        from claimlens.ocr import DocAiOcr

        ocr = DocAiOcr(settings.gcp_project, settings.docai_location, settings.docai_processor)
    else:
        from claimlens.ocr import NoOcr

        ocr = NoOcr()
    from claimlens.jobs import build_jobs

    deps = Deps(settings=settings, storage=storage, db=db, ai=ai, ocr=ocr, chat_ai=chat_ai)
    deps.jobs = build_jobs(settings, deps)
    return deps
