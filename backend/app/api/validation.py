from typing import Any

from flask import request

from app.errors import ApiError


def json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("invalid_json", "Send a JSON object.", 400)
    return data


def require_fields(data: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if data.get(field) in (None, "")]
    if missing:
        raise ApiError(
            "validation_error",
            "Required fields are missing.",
            400,
            {"fields": missing},
        )


def pagination_args(default_limit: int = 50, max_limit: int = 100):
    raw_limit = request.args.get("limit", str(default_limit))
    raw_offset = request.args.get("offset", "0")
    try:
        limit = int(raw_limit)
        offset = int(raw_offset)
    except (TypeError, ValueError):
        raise ApiError(
            "invalid_pagination",
            "Limit and offset must be numbers.",
            400,
        ) from None

    if limit < 1 or limit > max_limit or offset < 0:
        raise ApiError(
            "invalid_pagination",
            f"Limit must be between 1 and {max_limit} and offset must be zero or greater.",
            400,
        )
    return limit, offset


def optional_int_arg(name: str):
    raw = request.args.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ApiError(
            "invalid_pagination",
            f"{name} must be an integer.",
            400,
        ) from None
