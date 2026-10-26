from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db

health_api = Blueprint("health_api", __name__, url_prefix="/api/v1")

SERVICE_NAME = "projectpulse-api"


@health_api.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Health check database probe failed")
        return (
            jsonify(
                status="degraded",
                service=SERVICE_NAME,
                database="unavailable",
            ),
            503,
        )

    return jsonify(status="ok", service=SERVICE_NAME, database="ok")
