import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from claimlens import runner
from claimlens.api import router
from claimlens.deps import Deps, build_deps
from claimlens.settings import Settings


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="ClaimLens")
    app.state.deps = deps or build_deps(settings)
    app.state.start = runner.start

    # not /healthz: Cloud Run reserves paths ending in "z"
    @app.get("/health")
    def health():
        return {"ok": True}

    app.include_router(router)
    _serve_frontend(app, settings)
    return app


def _serve_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built React app; unknown paths get index.html so client-side routes survive a reload."""
    root = settings.frontend_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        return

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        if "." in path.rsplit("/", 1)[-1]:
            # a missing file (e.g. an old bundle after a redeploy) must not get HTML back
            raise HTTPException(404, "Not found")
        # never cache the shell, so a redeploy is picked up on the next load
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
