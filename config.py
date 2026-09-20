"""
FoodLoop configuration.

Loads settings from environment variables (via a .env file if present).
Falls back to a local SQLite database when no MySQL DATABASE_URL is configured,
so the project runs out of the box for local development / demos.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _build_database_uri():
    """Build the SQLAlchemy database URI.

    Priority:
    1. Explicit DATABASE_URL env var (e.g. a MySQL connection string)
    2. MySQL parts (MYSQL_HOST / MYSQL_USER / etc.) if MYSQL_HOST is set
    3. SQLite fallback stored under database/foodloop.db
    """
    explicit_url = os.environ.get("DATABASE_URL", "").strip()
    if explicit_url:
        return explicit_url

    mysql_host = os.environ.get("MYSQL_HOST", "").strip()
    if mysql_host:
        user = os.environ.get("MYSQL_USER", "root")
        password = os.environ.get("MYSQL_PASSWORD", "")
        port = os.environ.get("MYSQL_PORT", "3306")
        db = os.environ.get("MYSQL_DB", "foodloop")
        return f"mysql+pymysql://{user}:{password}@{mysql_host}:{port}/{db}"

    sqlite_path = os.path.join(BASE_DIR, "database", "foodloop.db")
    return f"sqlite:///{sqlite_path}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-not-for-production")

    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Uploaded donation images
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
