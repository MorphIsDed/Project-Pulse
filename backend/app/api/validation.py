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
