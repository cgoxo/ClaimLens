import logging
import re
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from claimlens import logs, runner
from claimlens.api import router
from claimlens.deps import Deps, build_deps
from claimlens.settings import Settings

request_log = logging.getLogger("claimlens.request")
CASE_PATH = re.compile(r"/api/cases/([^/]+)")


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or Settings()
    logs.setup(settings.app_env)
    app = FastAPI(title="ClaimLens")
    app.state.deps = deps or build_deps(settings)
    app.state.start = runner.start

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        status = response.status_code
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        case = CASE_PATH.match(path)
        request_log.log(level, "%s %s %s", request.method, path, status, extra={
            "user": getattr(request.state, "user", None), "method": request.method, "path": path,
            "status": status, "latency_ms": round((time.perf_counter() - start) * 1000),
            "case_id": case.group(1) if case else None})
        return response

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
