"""Run on the trusted application host: python -m scripts.recover_accounts demo|admin."""
import argparse
from getpass import getpass

from app.auth import hash_password
from app.config import APP_ENV
from app.db import db
from app.seed import DEMO_USERS, seed_defaults


def recover_demos():
    if APP_ENV != "local" or db.is_postgres:
        raise ValueError("Demo recovery requires local SQLite.")
    db.init_schema()
    seed_defaults()
    with db.connect() as conn:
        for uid, email, password, _, role, _ in DEMO_USERS:
            result = conn.execute(
                "UPDATE users SET password_hash=?,verified=1,active=1,token_version=token_version+1 "
                "WHERE id=? AND email=? AND role=?",
                (hash_password(password), uid, email, role),
            )
            if result.rowcount != 1:
                raise ValueError("Conflicting demo identity. No demo passwords were reset.")


def recover_admin(email, password):
    if len(password) < 12:
        raise ValueError("Use at least 12 characters.")
    with db.connect() as conn:
        result = conn.execute(db._sql(
            "UPDATE users SET password_hash=?,token_version=token_version+1 "
            "WHERE email=? AND role='admin' AND active=1 AND verified=1"
        ), (hash_password(password), email.strip().lower()))
        if result.rowcount != 1:
            raise ValueError("No active administrator matches that email.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["demo", "admin"])
    args = parser.parse_args()
    if args.mode == "demo":
        recover_demos()
    else:
        email = input("Admin email: ")
        password = getpass("New password: ")
        if password != getpass("Repeat password: "):
            raise SystemExit("Passwords differ.")
        recover_admin(email, password)
    print("Done.")
