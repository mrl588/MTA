import os
from pathlib import Path
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


def _sqlite_uri(filename: str) -> str:
    """
    Return an absolute SQLite URI.
    On Vercel the filesystem is read-only except /tmp, so we use /tmp there.
    Locally we use the backend/ directory.
    """
    if os.getenv("VERCEL"):
        return f"sqlite:////tmp/{filename}"
    return f"sqlite:///{_BASE_DIR / filename}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # If DATABASE_URL is set (e.g. Neon Postgres on Vercel), use it for user data.
    # Otherwise fall back to local SQLite.
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL if DATABASE_URL else _sqlite_uri("mta_transit.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MTA_API_KEY = os.getenv("MTA_API_KEY", "")
    FIREBASE_CREDENTIALS_PATH = os.getenv(
        "FIREBASE_CREDENTIALS_PATH", "firebase-service-account.json"
    )
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "nyc-transit-hub-4075d")

    # How old cached MTA data can be before we re-fetch (seconds)
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
