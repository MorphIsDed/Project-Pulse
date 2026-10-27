import json

from flask import Blueprint, Response, jsonify
from flask_login import current_user, login_required, logout_user

from app.api.validation import json_body
from app.services.account import (
    account_export_filename,
    delete_account,
    export_account,
)


accounts_api = Blueprint("accounts_api", __name__, url_prefix="/api/v1")


@accounts_api.get("/account/export")
@login_required
def get_account_export():
    return Response(
        json.dumps(export_account(current_user), indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": (
                "attachment; filename="
                f"{account_export_filename(current_user)}"
            )
        },
    )


@accounts_api.delete("/account")
@login_required
def delete_current_account():
    data = json_body()
    delete_account(current_user, data.get("password"))
    logout_user()
    return jsonify(message="Your account was deleted."), 200
