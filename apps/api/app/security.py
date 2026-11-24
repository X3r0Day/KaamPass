import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256

from fastapi import HTTPException, Request, Response
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError

from app.db.store import engine, run
from app.settings import firebase_app, settings

SESSION = "__Host-session"
CSRF = "__Host-csrf"
COOKIE = {"httponly": True, "secure": True, "samesite": "lax", "path": "/"}


@dataclass(frozen=True)
class Actor:
    uid: str
    phone: str
    provider: str = "firebase"


def claims_actor(claims):
    phone = claims.get("phone_number", "")
    if (
        not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone)
        or claims.get("firebase", {}).get("sign_in_provider") != "phone"
    ):
        raise HTTPException(401, "phone_required")
    return Actor(claims["sub"], phone)


def actor(request: Request) -> Actor:
    cookie = request.cookies.get(SESSION)
    if cookie and cookie.startswith("browser."):
        match = re.fullmatch(r"browser\.([a-f0-9]{32})\.([0-9]{12})\.([0-9]{10})\.([0-9a-f]{64})", cookie)
        if match and browser_enabled():
            uid, number, expiry, mac = match.groups()
            if int(expiry) > time.time() and hmac.compare_digest(
                mac, browser_signature(f"{uid}.{number}.{expiry}")
            ):
                return Actor(uid, "+999" + number, "browser")
        raise HTTPException(401, "sign_in")
    if not cookie or not settings().phone_auth_enabled:
        raise HTTPException(401, "sign_in")
    try:
        claims = auth.verify_session_cookie(cookie, check_revoked=True, app=firebase_app())
    except (FirebaseError, ValueError):
        raise HTTPException(401, "sign_in") from None
    return claims_actor(claims)


def browser_enabled():
    return (
        os.getenv("BROWSER_REGISTRATION_ENABLED", "true" if os.getenv("VERCEL") else "false").lower()
        == "true"
    )


def browser_signature(value):
    return hmac.new(settings().csrf_key, ("browser-session:" + value).encode(), sha256).hexdigest()


def new_browser_cookie():
    value = f"{secrets.token_hex(16)}.{secrets.randbelow(10**12):012d}.{int(time.time()) + 86400}"
    return f"browser.{value}.{browser_signature(value)}"


def signature(nonce: str, session: str) -> str:
    value = f"{sha256(session.encode()).hexdigest()}:{nonce}".encode()
    return hmac.new(settings().csrf_key, value, sha256).hexdigest()


def valid_csrf(token: str, session: str) -> bool:
    if not re.fullmatch(r"[a-f0-9]{48}\.[a-f0-9]{64}", token):
        return False
    nonce, mac = token.split(".")
    return hmac.compare_digest(mac, signature(nonce, session))


def issue_csrf(response: Response, session: str) -> str:
    nonce = secrets.token_hex(24)
    token = f"{nonce}.{signature(nonce, session)}"
    response.set_cookie(CSRF, token, max_age=86400, **COOKIE)
    return token


def rate_limit(bucket: str, identity: str, limit: int):
    key = hmac.new(settings().csrf_key, f"{bucket}:{identity}".encode(), sha256).hexdigest()
    period = int(time.time()) // 60
    with engine().begin() as db:
        hits = run(
            db,
            """INSERT INTO rate_buckets AS b (key,period,hits) VALUES (:key,:period,1)
            ON CONFLICT (key) DO UPDATE SET period=excluded.period,
            hits=CASE WHEN b.period=excluded.period THEN b.hits+1 ELSE 1 END RETURNING hits""",
            key=key,
            period=period,
        ).scalar_one()
        if secrets.randbelow(128) == 0:
            run(db, "DELETE FROM rate_buckets WHERE period < :old", old=period - 1440)
    if hits > limit:
        raise HTTPException(429, "slow_down", headers={"Retry-After": "60"})


def protect_write(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.method == "POST" and request.url.path == "/api/whatsapp/webhook":
        return  # Meta is authenticated against the exact request body by the webhook.
    if request.headers.get("origin") not in settings().origins:
        raise HTTPException(403, "origin")
    sent = request.headers.get("x-csrf-token", "")
    if not valid_csrf(sent, request.cookies.get(SESSION, "")) or not hmac.compare_digest(
        sent.encode(), request.cookies.get(CSRF, "").encode()
    ):
        raise HTTPException(403, "csrf")
    client = request.client.host if request.client else "local"
    if not settings().local:
        client = request.headers.get("x-vercel-forwarded-for", client).split(",")[0].strip()
    login = request.url.path in {"/api/auth/session", "/api/auth/browser"}
    rate_limit("login" if login else "write", client, 12 if login else 90)
