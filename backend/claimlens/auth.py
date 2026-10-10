"""Who is calling? Dev mode trusts a header; Firebase mode checks a signed ID token."""

from fastapi import HTTPException, Request

_firebase_app = None


def verify_firebase_token(token: str, project: str) -> dict:
    global _firebase_app
    import firebase_admin
    from firebase_admin import auth

    if _firebase_app is None:
        _firebase_app = firebase_admin.initialize_app(options={"projectId": project})
    return auth.verify_id_token(token, app=_firebase_app)


def current_user(request: Request) -> str:
    settings = request.app.state.deps.settings
    if settings.auth_mode == "dev":
        email = request.headers.get("X-Dev-User", "").strip().lower()
        if not email:
            raise HTTPException(401, "Missing X-Dev-User header")
        return email

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Sign in required")
    try:
        claims = verify_firebase_token(header.removeprefix("Bearer ").strip(), settings.gcp_project)
    except Exception:
        raise HTTPException(401, "Invalid or expired sign-in token")
    email = (claims.get("email") or "").lower()
    if not email or not claims.get("email_verified") or email not in settings.allowed_emails:
        raise HTTPException(403, "This account is not allowed to use ClaimLens")
    return email
