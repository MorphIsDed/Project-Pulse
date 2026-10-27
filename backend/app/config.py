import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

DEVELOPMENT_SECRET = "development-only-change-me"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = "development"
    SECRET_KEY = os.environ.get("SECRET_KEY", DEVELOPMENT_SECRET)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///projectpulse.sqlite3"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    ALLOW_PUBLIC_SIGNUP = env_bool("ALLOW_PUBLIC_SIGNUP", False)
    DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "DemoPulse123!")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:5173")
    MAIL_HOST = os.environ.get("MAIL_HOST")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_FROM = os.environ.get("MAIL_FROM")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)

    PROPAGATE_EXCEPTIONS = False


class DevelopmentConfig(Config):
    APP_ENV = "development"
    DEBUG = True


class TestingConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "testing-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    LOG_LEVEL = "WARNING"


class ProductionConfig(Config):
    APP_ENV = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SECRET_KEY = os.environ.get("SECRET_KEY")


CONFIG_CLASSES = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    selected = (name or os.environ.get("APP_ENV") or "development").lower()
    try:
        return CONFIG_CLASSES[selected]
    except KeyError as exc:
        raise ValueError(f"Unknown APP_ENV: {selected}") from exc
