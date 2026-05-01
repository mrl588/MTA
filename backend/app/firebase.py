import os
import json
import logging
from functools import wraps
from flask import request, jsonify, g

logger = logging.getLogger(__name__)
_firebase_initialized = False

# Firebase project info
FIREBASE_PROJECT_ID = "nyc-transit-hub-4075d"


def init_firebase():
    """
    Initialize Firebase Admin SDK.

    Supports two credential sources (checked in order):
    1. FIREBASE_SERVICE_ACCOUNT_JSON env var — full JSON string (preferred for Render/Vercel)
    2. FIREBASE_CREDENTIALS_PATH env var — path to a local JSON file (local dev)

    Skips gracefully with a warning if neither is available.
    """
    global _firebase_initialized
    try:
        import firebase_admin
        from firebase_admin import credentials

        # Option 1: JSON string in env var (production on Render)
        json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if json_str:
            try:
                service_account_info = json.loads(json_str)
                cred = credentials.Certificate(service_account_info)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT_JSON env var.")
                return
            except Exception as exc:
                logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON: %s", exc)
                return

        # Option 2: file path (local dev)
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-service-account.json")
        if not os.path.exists(cred_path):
            logger.warning(
                "Firebase credentials not found. "
                "Set FIREBASE_SERVICE_ACCOUNT_JSON (JSON string) or "
                "FIREBASE_CREDENTIALS_PATH (file path). "
                "Auth endpoints will return 503 until credentials are provided."
            )
            return

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized from file: %s", cred_path)

    except Exception as exc:
        logger.error("Failed to initialize Firebase: %s", exc)


def verify_token(f):
    """Decorator that verifies a Firebase ID token on protected routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _firebase_initialized:
            return jsonify({"error": "Auth service not configured"}), 503

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        id_token = auth_header.split("Bearer ")[1]
        try:
            from firebase_admin import auth
            decoded = auth.verify_id_token(id_token)
            g.firebase_uid = decoded["uid"]
            g.email = decoded.get("email", "")
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401

        return f(*args, **kwargs)
    return decorated
