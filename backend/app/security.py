from hashlib import sha256
import time

from flask import current_app, request

from app import get_db


def token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def rate_bucket(category: str, identity: str) -> str:
    return sha256(f"{category}:{identity}".encode("utf-8")).hexdigest()


def request_ip() -> str:
    return request.remote_addr or "unknown"


def rate_limited(bucket: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = int(time.time())
    row = get_db().execute(
        "SELECT window_started, attempts, blocked_until FROM auth_rate_limits WHERE bucket_key = ?",
        (bucket,),
    ).fetchone()
    if row is None:
        return False, 0
    if row["blocked_until"] > now:
        return True, row["blocked_until"] - now
    if now - row["window_started"] >= window_seconds:
        return False, 0
    if row["attempts"] >= limit:
        return True, max(1, row["window_started"] + window_seconds - now)
    return False, 0


def record_failure(bucket: str, limit: int, window_seconds: int) -> None:
    now = int(time.time())
    db = get_db()
    row = db.execute(
        "SELECT window_started, attempts FROM auth_rate_limits WHERE bucket_key = ?",
        (bucket,),
    ).fetchone()
    if row is None or now - row["window_started"] >= window_seconds:
        db.execute(
            "INSERT INTO auth_rate_limits(bucket_key, window_started, attempts, blocked_until) VALUES (?, ?, 1, 0) "
            "ON CONFLICT(bucket_key) DO UPDATE SET window_started=excluded.window_started, attempts=1, blocked_until=0",
            (bucket, now),
        )
    else:
        attempts = row["attempts"] + 1
        blocked_until = now + window_seconds if attempts >= limit else 0
        db.execute(
            "UPDATE auth_rate_limits SET attempts = ?, blocked_until = ? WHERE bucket_key = ?",
            (attempts, blocked_until, bucket),
        )
    db.commit()


def clear_rate_bucket(bucket: str) -> None:
    get_db().execute("DELETE FROM auth_rate_limits WHERE bucket_key = ?", (bucket,))
    get_db().commit()


def limited_response(retry_after: int):
    response = current_app.response_class(
        response='{"error":{"code":"rate_limited","message":"Too many attempts. Try again later."}}',
        status=429,
        mimetype="application/json",
    )
    response.headers["Retry-After"] = str(max(1, retry_after))
    return response
