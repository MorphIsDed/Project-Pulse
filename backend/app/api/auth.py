import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from app import get_db
from app.mail import send_email
from app.security import clear_rate_bucket, rate_bucket, rate_limited, record_failure, token_hash, limited_response, request_ip

auth_api = Blueprint("auth_api", __name__)

def issue_token(user_id, kind, url_key, subject, instruction, hours):
    db = get_db()
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    db.execute("DELETE FROM account_tokens WHERE user_id = ? AND kind = ?", (user_id, kind))
    db.execute("INSERT INTO account_tokens(user_id, kind, token_hash, expires_at) VALUES (?, ?, ?, ?)", (user_id, kind, token_hash(token), expires))
    db.commit()
    send_email(db.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()["email"], subject,
               f"{instruction}\n\n{current_app.config['PUBLIC_URL']}/?{url_key}={token}\n\nThis link expires in {hours} hours.")

@auth_api.post("/api/v1/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("display_name", "").strip()
    bucket = rate_bucket("register", request_ip())
    limited, retry = rate_limited(bucket, 5, 3600)
    if limited: return limited_response(retry)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not name or len(name)>120 or not isinstance(password,str) or len(password)<10:
        record_failure(bucket,5,3600)
        return jsonify(error={"code":"invalid_registration","message":"Enter a valid email, display name, and password of at least 10 characters."}),400
    db=get_db()
    try:
        cur=db.execute("INSERT INTO users(email,password_hash,display_name,email_verified_at) VALUES(?,?,?,NULL)",(email,generate_password_hash(password),name))
        db.commit()
    except Exception:
        db.rollback(); record_failure(bucket,5,3600)
        return jsonify(error={"code":"registration_failed","message":"An account with that email may already exist."}),409
    try: issue_token(cur.lastrowid,"email_verification","verify_token","Verify your ProjectPulse email","Verify your email address",24)
    except Exception:
        current_app.logger.exception("Verification email delivery failed")
        return jsonify(error={"code":"email_delivery_failed","message":"Your account was created. Configure email delivery, then request a new verification link."}),503
    return jsonify(message="Account created. Check your email to verify it before signing in."),201

@auth_api.post("/api/v1/auth/verify-email")
def verify_email():
    token=(request.get_json(silent=True) or {}).get("token","")
    db=get_db(); row=db.execute("SELECT user_id,expires_at FROM account_tokens WHERE kind='email_verification' AND token_hash=?",(token_hash(token),)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return jsonify(error={"code":"invalid_token","message":"This verification link is invalid or expired."}),400
    db.execute("UPDATE users SET email_verified_at=CURRENT_TIMESTAMP WHERE id=?",(row["user_id"],)); db.execute("DELETE FROM account_tokens WHERE user_id=? AND kind='email_verification'",(row["user_id"],)); db.commit()
    return jsonify(message="Email verified. You can now sign in."),200

@auth_api.post("/api/v1/auth/resend-verification")
def resend_verification():
    data=request.get_json(silent=True) or {}; email=str(data.get("email","")).strip().lower(); bucket=rate_bucket("resend",request_ip()); limited,retry=rate_limited(bucket,5,3600)
    if limited:return limited_response(retry)
    record_failure(bucket,5,3600)
    row=get_db().execute("SELECT id FROM users WHERE email=? COLLATE NOCASE AND email_verified_at IS NULL",(email,)).fetchone()
    if row:
        try: issue_token(row["id"],"email_verification","verify_token","Verify your ProjectPulse email","Verify your email address",24)
        except Exception: current_app.logger.exception("Resend verification email failed")
    return jsonify(message="If the account needs verification, a link will be sent."),200

@auth_api.post("/api/v1/auth/request-password-reset")
def request_password_reset():
    email=str((request.get_json(silent=True) or {}).get("email","")).strip().lower(); bucket=rate_bucket("reset",request_ip()); limited,retry=rate_limited(bucket,5,3600)
    if limited:return limited_response(retry)
    record_failure(bucket,5,3600)
    row=get_db().execute("SELECT id FROM users WHERE email=? COLLATE NOCASE",(email,)).fetchone()
    if row:
        try: issue_token(row["id"],"password_reset","reset_token","Reset your ProjectPulse password","Choose a new password",1)
        except Exception: current_app.logger.exception("Password reset email failed")
    return jsonify(message="If an account exists, a password reset link will be sent."),200

@auth_api.post("/api/v1/auth/reset-password")
def reset_password():
    data=request.get_json(silent=True) or {}; token=data.get("token",""); password=data.get("password","")
    if not isinstance(password,str) or len(password)<10:return jsonify(error={"code":"weak_password","message":"Use a password with at least 10 characters."}),400
    db=get_db(); row=db.execute("SELECT user_id,expires_at FROM account_tokens WHERE kind='password_reset' AND token_hash=?",(token_hash(token),)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"])<datetime.now(timezone.utc):return jsonify(error={"code":"invalid_token","message":"This reset link is invalid or expired."}),400
    db.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(password),row["user_id"])); db.execute("DELETE FROM account_tokens WHERE user_id=?",(row["user_id"],)); db.commit()
    return jsonify(message="Password updated. Sign in with your new password."),200

@auth_api.post("/api/v1/auth/login")
def login():
    data=request.get_json(silent=True) or {}; email=str(data.get("email","")).strip().lower(); password=data.get("password","")
    ip_bucket=rate_bucket("login-ip",request_ip()); email_bucket=rate_bucket("login-email",email)
    checks=[rate_limited(ip_bucket,20,900),rate_limited(email_bucket,5,900)]
    if any(item[0] for item in checks):return limited_response(max(item[1] for item in checks))
    user=get_db().execute("SELECT id,email,password_hash,display_name,email_verified_at FROM users WHERE email=? COLLATE NOCASE",(email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"],password):
        record_failure(ip_bucket,20,900); record_failure(email_bucket,5,900)
        return jsonify(error={"code":"invalid_credentials","message":"Email or password is incorrect."}),401
    if not user["email_verified_at"]:return jsonify(error={"code":"email_verification_required","message":"Verify your email before signing in."}),403
    clear_rate_bucket(ip_bucket);clear_rate_bucket(email_bucket);session.clear();session["user_id"]=user["id"]
    return jsonify(user={"id":user["id"],"email":user["email"],"display_name":user["display_name"],"email_verified":True}),200

@auth_api.post("/api/v1/auth/logout")
def logout():session.clear();return jsonify(message="Logged out."),200

@auth_api.get("/api/v1/auth/me")
def me():
    user_id=session.get("user_id")
    if user_id is None:return jsonify(user=None),200
    user=get_db().execute("SELECT id,email,display_name,email_verified_at FROM users WHERE id=?",(user_id,)).fetchone()
    return jsonify(user={"id":user["id"],"email":user["email"],"display_name":user["display_name"],"email_verified":bool(user["email_verified_at"]),"email_verified_at":user["email_verified_at"]} if user else None),200
