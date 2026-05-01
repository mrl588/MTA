"""
Vercel serverless entry point.
Vercel looks for a WSGI app exported as `app` from api/index.py.
"""
import sys
import os

# Make sure the backend/ root is on the path so `app` package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app

app = create_app()
