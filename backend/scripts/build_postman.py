"""Write the Postman collection and the local/cloud environments into postman/."""

import argparse
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "postman"
SAMPLES = ROOT / "samples"
IDT = "https://identitytoolkit.googleapis.com"

AUTH_SCRIPT = [
    "// Local: send X-Dev-User. Cloud: send the Firebase ID token from 'Sign in test user'.",
    "const devUser = pm.environment.get('devUser');",
    "if (devUser) { pm.request.headers.upsert({key: 'X-Dev-User', value: devUser}); }",
    "else if (pm.environment.get('idToken')) {",
    "  pm.request.headers.upsert({key: 'Authorization', value: 'Bearer ' + pm.environment.get('idToken')});",
    "}",
]


def url(path: str, host: str = "{{baseUrl}}") -> dict:
    return {"raw": f"{host}/{path}", "host": [host], "path": path.split("/")}


def req(name, method, path, body=None, tests=None, host="{{baseUrl}}", description=""):
    item = {"name": name, "request": {"method": method, "header": [], "url": url(path, host),
                                      "description": description}}
    if body:
        item["request"]["body"] = body
    if tests:
        item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}]
    return item


def collection() -> dict:
    sign_in = req(
        "Sign in test user (cloud only)", "POST", "v1/accounts:signInWithPassword?key={{firebaseApiKey}}",
        host=IDT,
        body={"mode": "raw", "options": {"raw": {"language": "json"}},
              "raw": json.dumps({"email": "{{testEmail}}", "password": "{{testPassword}}",
                                 "returnSecureToken": True}, indent=2)},
        tests=["pm.test('signed in', () => pm.response.to.have.status(200));",
               "pm.environment.set('idToken', pm.response.json().idToken);"],
        description="Gets a Firebase ID token for the email/password test user and stores it as idToken.")
    sign_in["request"]["auth"] = {"type": "noauth"}
    files = {"mode": "formdata", "formdata": [
        {"key": "claim", "type": "file", "src": str(SAMPLES / "claim.pdf")},
        {"key": "policy", "type": "file", "src": str(SAMPLES / "policy.pdf")}]}
    return {
        "info": {"_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "claimlens")), "name": "ClaimLens",
                 "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                 "description": "ClaimLens backend. Pick the 'ClaimLens local' or 'ClaimLens cloud' environment. "
                                "Cloud: run 'Sign in test user' first."},
        "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": AUTH_SCRIPT}}],
        "item": [
            sign_in,
            req("Health", "GET", "health"),
            req("Me", "GET", "api/me"),
            req("Create case (sample claim + policy)", "POST", "api/cases", body=files,
                tests=["pm.test('created', () => pm.response.to.have.status(201));",
                       "pm.environment.set('caseId', pm.response.json().case_id);"],
                description="Uploads samples/claim.pdf and samples/policy.pdf. Then run 'Get case' until READY."),
            req("Get case", "GET", "api/cases/{{caseId}}",
                tests=["const c = pm.response.json();",
                       "console.log(c.status, c.score, c.risk, (c.findings || []).length + ' findings');",
                       "pm.test('status ' + c.status, () => pm.expect(['QUEUED','READING','CHECKING','PROVING','READY']).to.include(c.status));",
                       "if (c.findings && c.findings.length) { pm.environment.set('findingId', c.findings[0].id); }"],
                description="Poll until status is READY. Stores the first finding's id."),
            req("List my cases", "GET", "api/cases"),
            req("Page image (claim p.3)", "GET", "api/cases/{{caseId}}/pages/claim/3.png"),
            req("Review first finding", "POST", "api/cases/{{caseId}}/findings/{{findingId}}/review",
                body={"mode": "raw", "options": {"raw": {"language": "json"}},
                      "raw": json.dumps({"action": "accept", "note": "checked against the bill"}, indent=2)}),
        ],
    }


def environment(name: str, values: dict) -> dict:
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name)), "name": name, "_postman_variable_scope": "environment",
            "values": [{"key": k, "value": v, "type": "secret" if "Password" in k or k == "idToken" else "default",
                        "enabled": True} for k, v in values.items()]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud-url", default="https://<claimlens-api url>")
    ap.add_argument("--api-key", default="", help="Firebase web API key")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    files = {
        "ClaimLens.postman_collection.json": collection(),
        "ClaimLens-local.postman_environment.json": environment("ClaimLens local", {
            "baseUrl": "http://localhost:8080", "devUser": "you@example.com", "caseId": "", "findingId": ""}),
        "ClaimLens-cloud.postman_environment.json": environment("ClaimLens cloud", {
            "baseUrl": args.cloud_url, "firebaseApiKey": args.api_key, "testEmail": "claimlens-tester@example.com",
            "testPassword": "", "idToken": "", "devUser": "", "caseId": "", "findingId": ""}),
    }
    for name, data in files.items():
        (OUT / name).write_text(json.dumps(data, indent=2) + "\n")
        print("wrote", OUT / name)
