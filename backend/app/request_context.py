import time
import uuid

from flask import Flask, g, request


def register_request_context(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        incoming = request.headers.get("X-Request-ID", "").strip()
        g.request_id = incoming[:128] if incoming else uuid.uuid4().hex
        g.request_started_at = time.perf_counter()

    @app.after_request
    def log_request(response):
        request_id = getattr(g, "request_id", "")
        started_at = getattr(g, "request_started_at", None)
        duration_ms = (
            (time.perf_counter() - started_at) * 1000 if started_at else 0.0
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id

        level = app.logger.debug if request.path.endswith("/health") else app.logger.info
        level(
            "%s %s %s %.1fms request_id=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
