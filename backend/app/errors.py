from typing import Any

from flask import Flask, g, jsonify
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
}


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def error_response(
    code: str,
    message: str,
    status: int,
    details: Any | None = None,
):
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    request_id = getattr(g, "request_id", None)
    if request_id:
        error["request_id"] = request_id
    return jsonify(error=error), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return error_response(exc.code, exc.message, exc.status, exc.details)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(exc: CSRFError):
        return error_response(
            "csrf_error", exc.description or "Invalid or missing CSRF token.", 400
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        status = exc.code or 500
        code = HTTP_ERROR_CODES.get(status, "http_error")
        message = exc.description or "The request could not be completed."
        if status >= 500:
            message = "An unexpected error occurred."
        return error_response(code, message, status)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled exception", exc_info=exc)
        return error_response(
            "internal_error", "An unexpected error occurred.", 500
        )
