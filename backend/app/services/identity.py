import re

from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import ApiError
from app.extensions import db
from app.models.user import User

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL_LENGTH = 320
MAX_PASSWORD_LENGTH = 128
MIN_PASSWORD_LENGTH = 8
MAX_DISPLAY_NAME_LENGTH = 80

DEMO_USERS = (
    ("owner@demo.local", "Demo Owner"),
    ("editor@demo.local", "Demo Editor"),
    ("viewer@demo.local", "Demo Viewer"),
)

_DUMMY_HASH = generate_password_hash("not-a-real-password")


def normalize_email(value) -> str:
    if not isinstance(value, str):
        raise ApiError("invalid_email", "Enter a valid email address.", 400)

    email = value.strip().lower()
    if len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.fullmatch(email):
        raise ApiError("invalid_email", "Enter a valid email address.", 400)
    return email


def validate_password(value) -> str:
    if not isinstance(value, str):
        raise ApiError("weak_password", "Password must be a string.", 400)
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ApiError(
            "weak_password",
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            400,
        )
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ApiError(
            "weak_password",
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters.",
            400,
        )
    return value


def validate_display_name(value) -> str:
    if not isinstance(value, str):
        raise ApiError("validation_error", "Display name must be a string.", 400)

    display_name = value.strip()
    if not display_name:
        raise ApiError("validation_error", "Display name cannot be empty.", 400)
    if len(display_name) > MAX_DISPLAY_NAME_LENGTH:
        raise ApiError(
            "validation_error",
            f"Display name must be at most {MAX_DISPLAY_NAME_LENGTH} characters.",
            400,
        )
    return display_name


def create_user(email, password, display_name) -> User:
    normalized_email = normalize_email(email)
    valid_password = validate_password(password)
    valid_display_name = validate_display_name(display_name)

    user = User(email=normalized_email, display_name=valid_display_name)
    user.set_password(valid_password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "email_taken",
            "An account with this email already exists.",
            409,
        ) from None

    return user


def authenticate(email, password) -> User | None:
    if not isinstance(email, str) or not isinstance(password, str):
        return None

    normalized_email = email.strip().lower()
    user = db.session.execute(
        db.select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        return None

    if not user.is_active:
        return None

    if not user.check_password(password):
        return None

    return user


def seed_demo_users(password: str) -> tuple[int, int]:
    valid_password = validate_password(password)
    created = 0
    skipped = 0

    for email, display_name in DEMO_USERS:
        existing = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        user = User(email=email, display_name=display_name)
        user.set_password(valid_password)
        db.session.add(user)
        created += 1

    db.session.commit()
    return created, skipped
