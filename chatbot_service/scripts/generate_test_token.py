"""
Generate a JWT token for manual testing of the FastAPI chatbot service.

Usage:
    python scripts/generate_test_token.py [user_email] [role1,role2,...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt

from app.config import settings


def generate(user: str, roles: list[str], ttl: int = 600) -> str:
    payload = {
        "user": user,
        "roles": roles,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "Administrator"
    roles = sys.argv[2].split(",") if len(sys.argv) > 2 else ["System Manager"]
    print(generate(user, roles))
