"""Add the Cloud Run hosts to Firebase Auth's authorized domains (needed for Google sign-in there). Safe to re-run."""

import json
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse

PROJECT, REGION, SERVICE = "social-pulse-510513", "asia-south1", "claimlens-api"
API = f"https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}/config"


def sh(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def call(method: str, url: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None, headers={
        "Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as res:
        return json.load(res)


if __name__ == "__main__":
    urls = json.loads(sh("gcloud", "run", "services", "describe", SERVICE, "--project", PROJECT, "--region", REGION,
                         "--format", 'value(metadata.annotations."run.googleapis.com/urls")'))
    hosts = sorted({urlparse(u).hostname for u in urls})
    token = sh("gcloud", "auth", "print-access-token")
    current = call("GET", API, token).get("authorizedDomains", [])
    missing = [h for h in hosts if h not in current]
    if not missing:
        print("already authorized:", ", ".join(hosts))
        sys.exit(0)
    call("PATCH", f"{API}?updateMask=authorizedDomains", token, {"authorizedDomains": current + missing})
    print("added:", ", ".join(missing))
