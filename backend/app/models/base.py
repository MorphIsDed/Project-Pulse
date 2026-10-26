from datetime import datetime, timezone
from sqlalchemy import func

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntPKMixin:
    id = db.Column(db.Integer, primary_key=True)


class TimestampMixin:
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now()
    )
