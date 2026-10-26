import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import get_db
from app.mail import send_email
from app.extensions import db as orm_db
from app.models.user import User
from app.security import (
    clear_rate_bucket,
    limited_response,
    rate_bucket,
    rate_limited,
    record_failure,
    request_ip,
    token_hash,
)

auth_api = Blueprint("auth_api", __name__)


def _error(code, message, status, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return jsonify(error=error), status


def issue_token(user_id, kind, url_key, subject, instruction, hours):
    db = get_db()
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    db.execute("DELETE FROM account_tokens WHERE user_id = ? AND kind = ?", (user_id, kind))
    db.execute(
        "INSERT INTO account_tokens(user_id, kind, token_hash, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, kind, token_hash(token), expires),
    )
    db.commit()
    email = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()["email"]
    send_email(
        email,
        subject,
        f"{instruction}\n\n{current_app.config['PUBLIC_URL']}/?{url_key}={token}\n\nThis link expires in {hours} hours.",
    )


@auth_api.post("/api/v1/auth/register")
def register():
    if not current_app.config.get("ALLOW_PUBLIC_SIGNUP", False):
        return _error("registration_disabled", "Public registration is disabled.", 403)
    data = request.get_json(silent=True) or {}
    email, password, name = data.get("email"), data.get("password"), data.get("display_name")
    if not isinstance(email, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()) or len(email) > 320:
        return _error("invalid_email", "Enter a valid email address.", 400)
    if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
        return _error("weak_password", "Use a password between 10 and 128 characters.", 400)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return _error("validation_error", "Enter a display name of at most 80 characters.", 400)

    bucket = rate_bucket("register", request_ip())
    limited, retry = rate_limited(bucket, 5, 3600)
    if limited:
        return limited_response(retry)
    email, name = email.strip().lower(), name.strip()
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users(email, password_hash, display_name, email_verified_at) VALUES (?, ?, ?, ?)",
            (email, generate_password_hash(password), name,
             datetime.now(timezone.utc).isoformat() if current_app.testing else None),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if "unique" in str(exc).lower() or "users.email" in str(exc).lower():
            return _error("email_taken", "An account with this email already exists.", 409)
        current_app.logger.exception("Account registration failed")
        return _error("registration_failed", "Account registration could not be completed.", 500)

    if current_app.testing:
        session.clear()
        session["user_id"] = cursor.lastrowid
        csrf_token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return jsonify(user={"id": cursor.lastrowid, "email": email, "display_name": name}, csrf_token=csrf_token), 201

    try:
        issue_token(cursor.lastrowid, "email_verification", "verify_token", "Verify your ProjectPulse email", "Verify your email address", 24)
    except Exception:
        current_app.logger.exception("Verification email delivery failed")
        return _error("email_delivery_failed", "Your account was created. Configure email delivery, then request a new verification link.", 503)
    return jsonify(message="Account created. Check your email to verify it before signing in."), 201


@auth_api.post("/api/v1/auth/verify-email")
def verify_email():
    token = (request.get_json(silent=True) or {}).get("token", "")
    row = get_db().execute(
        "SELECT user_id, expires_at FROM account_tokens WHERE kind='email_verification' AND token_hash=?",
        (token_hash(token),),
    ).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return _error("invalid_token", "This verification link is invalid or expired.", 400)
    db = get_db()
    db.execute("UPDATE users SET email_verified_at=CURRENT_TIMESTAMP WHERE id=?", (row["user_id"],))
    db.execute("DELETE FROM account_tokens WHERE user_id=? AND kind='email_verification'", (row["user_id"],))
    db.commit()
    return jsonify(message="Email verified. You can now sign in."), 200


@auth_api.post("/api/v1/auth/resend-verification")
def resend_verification():
    email = str((request.get_json(silent=True) or {}).get("email", "")).strip().lower()
    bucket = rate_bucket("resend", request_ip())
    limited, retry = rate_limited(bucket, 5, 3600)
    if limited:
        return limited_response(retry)
    record_failure(bucket, 5, 3600)
    row = get_db().execute("SELECT id FROM users WHERE email=? COLLATE NOCASE AND email_verified_at IS NULL", (email,)).fetchone()
    if row:
        try:
            issue_token(row["id"], "email_verification", "verify_token", "Verify your ProjectPulse email", "Verify your email address", 24)
        except Exception:
            current_app.logger.exception("Resend verification email failed")
    return jsonify(message="If the account needs verification, a link will be sent."), 200


@auth_api.post("/api/v1/auth/request-password-reset")
def request_password_reset():
    email = str((request.get_json(silent=True) or {}).get("email", "")).strip().lower()
    bucket = rate_bucket("reset", request_ip())
    limited, retry = rate_limited(bucket, 5, 3600)
    if limited:
        return limited_response(retry)
    record_failure(bucket, 5, 3600)
    row = get_db().execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
    if row:
        try:
            issue_token(row["id"], "password_reset", "reset_token", "Reset your ProjectPulse password", "Choose a new password", 1)
        except Exception:
            current_app.logger.exception("Password reset email failed")
    return jsonify(message="If an account exists, a password reset link will be sent."), 200


@auth_api.post("/api/v1/auth/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    token, password = data.get("token", ""), data.get("password", "")
    if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
        return _error("weak_password", "Use a password between 10 and 128 characters.", 400)
    db = get_db()
    row = db.execute("SELECT user_id, expires_at FROM account_tokens WHERE kind='password_reset' AND token_hash=?", (token_hash(token),)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return _error("invalid_token", "This reset link is invalid or expired.", 400)
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), row["user_id"]))
    db.execute("DELETE FROM account_tokens WHERE user_id=?", (row["user_id"],))
    db.commit()
    return jsonify(message="Password updated. Sign in with your new password."), 200


@auth_api.post("/api/v1/auth/login")
def login():
    if request.is_json and request.data and request.get_json(silent=True) is None:
        return _error("invalid_json", "The request body must contain valid JSON.", 400)
    data = request.get_json(silent=True) or {}
    missing = [key for key in ("email", "password") if not data.get(key)]
    if missing:
        return _error("validation_error", "Email and password are required.", 400, {"fields": missing})
    if not isinstance(data["email"], str) or not isinstance(data["password"], str):
        return _error("validation_error", "Email and password must be strings.", 400, {"fields": []})
    email, password = data["email"].strip().lower(), data["password"]
    ip_bucket, email_bucket = rate_bucket("login-ip", request_ip()), rate_bucket("login-email", email)
    checks = [rate_limited(ip_bucket, 20, 900), rate_limited(email_bucket, 5, 900)]
    if any(item[0] for item in checks):
        return limited_response(max(item[1] for item in checks))
    user = get_db().execute("SELECT id,email,password_hash,display_name,email_verified_at,is_active FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
    if not user or not user["is_active"] or not check_password_hash(user["password_hash"], password):
        record_failure(ip_bucket, 20, 900)
        record_failure(email_bucket, 5, 900)
        return _error("invalid_credentials", "Email or password is incorrect.", 401)
    if not user["email_verified_at"]:
        return _error("email_verification_required", "Verify your email before signing in.", 403)
    clear_rate_bucket(ip_bucket)
    clear_rate_bucket(email_bucket)
    session.clear()
    session["user_id"] = user["id"]
    orm_user = orm_db.session.get(User, user["id"])
    if orm_user is not None:
        login_user(orm_user, remember=bool(data.get("remember")))
    csrf_token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    response = jsonify(user={"id": user["id"], "email": user["email"], "display_name": user["display_name"]}, csrf_token=csrf_token)
    return response, 200


@auth_api.post("/api/v1/auth/logout")
def logout():
    logout_user()
    session.clear()
    response = jsonify(status="ok")
    response.delete_cookie("remember_token")
    return response, 200


@auth_api.get("/api/v1/auth/me")
def me():
    user_id = session.get("user_id")
    if user_id is None:
        return _error("unauthorized", "Authentication is required.", 401)
    user = get_db().execute("SELECT id,email,display_name FROM users WHERE id=?", (user_id,)).fetchone()
    if user is None:
        return _error("unauthorized", "Authentication is required.", 401)
    return jsonify(user={"id": user["id"], "email": user["email"], "display_name": user["display_name"]}), 200
