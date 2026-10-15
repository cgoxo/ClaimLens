"""Background jobs. The API only calls `deps.jobs.enqueue(kind, payload)`; where the job runs is a setting:

inline      run now, in the request (tests)
thread      run in a daemon thread of this process (local development)
cloudtasks  a Cloud Tasks HTTP task calls back POST /internal/jobs/{kind} (production: survives restarts)

A new kind of job is one entry in HANDLERS.
"""

import json
import logging
import threading
from collections.abc import Callable
from datetime import timedelta

from claimlens.pipeline.run import run_pipeline

log = logging.getLogger(__name__)


def run_case_job(payload: dict, deps, attempt: int) -> None:
    """Analyse a case, at most once per delivery: a queue may deliver the same task twice."""
    case_id = payload["case_id"]
    if not deps.db.claim_run(case_id, attempt):
        log.info("case %s: delivery %s skipped, already claimed", case_id, attempt)
        return
    run_pipeline(case_id, deps)


HANDLERS: dict[str, Callable[[dict, object, int], None]] = {"run_case": run_case_job}


class InlineJobs:
    def __init__(self, deps):
        self.deps = deps

    def enqueue(self, kind: str, payload: dict) -> None:
        HANDLERS[kind](payload, self.deps, 0)


class ThreadJobs(InlineJobs):
    def enqueue(self, kind: str, payload: dict) -> None:
        threading.Thread(target=HANDLERS[kind], args=(payload, self.deps, 0), daemon=True, name=f"job-{kind}").start()


class CloudTasksJobs:
    def __init__(self, settings, client=None):
        self.settings = settings
        if client is None:
            from google.cloud import tasks_v2

            client = tasks_v2.CloudTasksClient()
        self.client = client

    def enqueue(self, kind: str, payload: dict) -> None:
        s = self.settings
        self.client.create_task(
            parent=f"projects/{s.gcp_project}/locations/{s.tasks_location}/queues/{s.tasks_queue}",
            task={
                "http_request": {
                    "http_method": "POST",
                    "url": f"{s.service_url}/internal/jobs/{kind}",
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode(),
                    "oidc_token": {"service_account_email": s.tasks_sa, "audience": s.service_url},
                },
                "dispatch_deadline": timedelta(minutes=30),
            },
        )


def verify_task_token(authorization: str, settings) -> bool:
    """True only for a Google-signed token minted for our tasks account, addressed to this service."""
    try:
        from google.auth.transport import requests
        from google.oauth2 import id_token

        token = authorization.removeprefix("Bearer ").strip()
        claims = id_token.verify_oauth2_token(token, requests.Request(), audience=settings.service_url)
        return claims.get("email") == settings.tasks_sa and bool(claims.get("email_verified", True))
    except Exception:
        return False


def build_jobs(settings, deps):
    if settings.jobs == "cloudtasks":
        return CloudTasksJobs(settings)
    return (InlineJobs if settings.jobs == "inline" else ThreadJobs)(deps)
