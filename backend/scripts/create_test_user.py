"""Create (if missing) the Firebase email/password user that Postman and the smoke test sign in with."""

import argparse
import sys

import firebase_admin
from firebase_admin import auth

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default="claimlens-tester@example.com")
    ap.add_argument("--password", required=True)
    ap.add_argument("--project", default="social-pulse-510513")
    args = ap.parse_args()
    firebase_admin.initialize_app(options={"projectId": args.project})
    try:
        user = auth.get_user_by_email(args.email)
        auth.update_user(user.uid, password=args.password, email_verified=True)
        print(f"updated password for {args.email}")
    except auth.UserNotFoundError:
        try:
            auth.create_user(email=args.email, password=args.password, email_verified=True)
        except auth.ConfigurationNotFoundError:
            sys.exit("Email/Password sign-in is not enabled. Firebase console -> Authentication -> Sign-in method.")
        print(f"created {args.email}")
