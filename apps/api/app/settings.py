from dataclasses import dataclass
from functools import lru_cache
import json
import os
from urllib.parse import urlsplit

import firebase_admin
from firebase_admin import credentials


@dataclass(frozen=True)
class Settings:
    project: str
    origins: frozenset[str]
    csrf_key: bytes
    local: bool


@lru_cache
def settings():
    local = not os.getenv("VERCEL") and os.getenv("APP_ENV") in {"local", "test"}
    project = os.environ["FIREBASE_PROJECT_ID"]
    emulator = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")
    if emulator and (not local or not project.startswith("demo-") or
                     urlsplit("//" + emulator).hostname not in {"localhost", "127.0.0.1"}):
        raise RuntimeError("Auth emulation requires a local demo project")
    if not local and (project.startswith("demo-") or os.getenv("NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL")):
        raise RuntimeError("Emulator settings are disabled on deployments")
    origins = frozenset(s.strip() for s in os.environ["WEB_ORIGINS"].split(","))
    for origin in origins:
        parsed = urlsplit(origin)
        if not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or "*" in origin:
            raise RuntimeError("Use exact web origins")
        if parsed.scheme != "https" and not (local and parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
            raise RuntimeError("Use HTTPS origins on deployments")
    key = os.environ["CSRF_SECRET"].encode()
    if len(key) < 32:
        raise RuntimeError("CSRF_SECRET must have at least 32 bytes")
    return Settings(project, origins, key, local)


@lru_cache
def firebase_app():
    config = settings()
    raw = os.getenv("FIREBASE_ADMIN_JSON")
    cred = credentials.Certificate(json.loads(raw)) if raw else None
    return firebase_admin.initialize_app(cred, {"projectId": config.project}, name="kaampaas")
