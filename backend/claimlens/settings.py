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

    max_file_mb: int = 20
    max_pages: int = 80
    max_files: int = 40
    max_bill_cards: int = 10
    daily_case_limit: int = 20

    @model_validator(mode="after")
    def _check(self):
        if self.storage == "gcs" and not self.bucket:
            raise ValueError("STORAGE=gcs needs BUCKET")
        if self.ocr == "docai" and not self.docai_processor:
            raise ValueError("OCR=docai needs DOCAI_PROCESSOR")
        if self.auth_mode == "dev" and self.app_env == "prod":
            raise ValueError("AUTH_MODE=dev is not allowed when APP_ENV=prod")
        return self
