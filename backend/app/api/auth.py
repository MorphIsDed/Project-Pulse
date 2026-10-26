from flask import Blueprint, current_app, g, jsonify
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf

from app.api.validation import json_body, require_fields
from app.errors import ApiError
from app.services.identity import authenticate, create_user

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/v1/auth")


@auth_api.get("/csrf")
def csrf_token():
    return jsonify(csrf_token=generate_csrf())


@auth_api.post("/register")
def register():
    if not current_app.config.get("ALLOW_PUBLIC_SIGNUP", False):
        raise ApiError(
            "registration_disabled",
            "Public registration is currently disabled.",
            403,
        )

    data = json_body()
    require_fields(data, "email", "password", "display_name")

    user = create_user(data["email"], data["password"], data["display_name"])
    login_user(user)

    return (
        jsonify(user=user.to_dict(), csrf_token=generate_csrf()),
        201,
    )


@auth_api.post("/login")
def login():
    data = json_body()
    require_fields(data, "email", "password")

    remember = data.get("remember", False)
    if not isinstance(remember, bool):
        raise ApiError("validation_error", "remember must be a boolean.", 400)

    user = authenticate(data["email"], data["password"])
    if user is None:
        current_app.logger.info(
            "auth.login.failed request_id=%s", getattr(g, "request_id", "")
        )
        raise ApiError(
            "invalid_credentials",
            "Email or password is incorrect.",
            401,
        )

    login_user(user, remember=remember)
    current_app.logger.info(
        "auth.login.succeeded user_id=%s request_id=%s",
        user.id,
        getattr(g, "request_id", ""),
    )

    return jsonify(user=user.to_dict(), csrf_token=generate_csrf())


@auth_api.post("/logout")
def logout():
    logout_user()
    current_app.logger.info(
        "auth.logout request_id=%s", getattr(g, "request_id", "")
    )
    return jsonify(status="ok")


@auth_api.get("/me")
@login_required
def me():
    return jsonify(user=current_user.to_dict())
