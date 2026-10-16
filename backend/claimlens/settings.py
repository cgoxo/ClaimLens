from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "prod"] = "local"
    storage: Literal["local", "gcs"] = "local"
    db: Literal["local", "firestore"] = "local"
    ai: Literal["vertex", "fake"] = "vertex"
    ocr: Literal["off", "docai"] = "off"
    auth_mode: Literal["dev", "firebase"] = "dev"
    jobs: Literal["inline", "thread", "cloudtasks"] = "thread"
    bill_story: Literal["on", "off"] = "off"
    chat: Literal["on", "off"] = "on"

    data_dir: Path = Path("./data")
    fake_ai_dir: Path = BACKEND_DIR / "tests" / "fixtures" / "ai" / "sample"
    frontend_dir: Path = BACKEND_DIR.parent / "frontend" / "dist"

    gcp_project: str = "social-pulse-510513"
    bucket: str | None = None
    firestore_db: str = "claimlens"
    gemini_model: str = "gemini-2.5-flash"
    vertex_location: str = "global"
    docai_location: str = "us"
    docai_processor: str | None = None
    tasks_queue: str = "claimlens-jobs"
    tasks_location: str = "asia-south1"
    tasks_sa: str | None = None  # the account Cloud Tasks signs its calls with
    service_url: str | None = None  # this service's public URL: where tasks call back

    max_file_mb: int = 20
    max_pages: int = 80
    max_files: int = 40
    daily_case_limit: int = 20
    chat_max_tools: int = 6
    chat_seconds: int = 60
    chat_history: int = 20
    chat_max_chars: int = 2000
    chat_daily_limit: int = 200
    chat_tool_chars: int = 8000

    @model_validator(mode="after")
    def _check(self):
        if self.storage == "gcs" and not self.bucket:
            raise ValueError("STORAGE=gcs needs BUCKET")
        if self.ocr == "docai" and not self.docai_processor:
            raise ValueError("OCR=docai needs DOCAI_PROCESSOR")
        if self.jobs == "cloudtasks" and not (self.tasks_sa and self.service_url):
            raise ValueError("JOBS=cloudtasks needs TASKS_SA and SERVICE_URL")
        if self.auth_mode == "dev" and self.app_env == "prod":
            raise ValueError("AUTH_MODE=dev is not allowed when APP_ENV=prod")
        return self
