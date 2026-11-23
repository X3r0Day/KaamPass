import time
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from pydantic import BaseModel, ConfigDict, Field

from app.security import COOKIE, CSRF, SESSION, Actor, actor, claims_actor, issue_csrf, valid_csrf
from app.settings import firebase_app

router = APIRouter(prefix="/api/auth")


class Exchange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=10, max_length=10000)


class CsrfToken(BaseModel):
    token: str


@router.get("/csrf", response_model=CsrfToken)
def csrf(request: Request, response: Response):
    cookie = request.cookies.get(SESSION, "")
    existing = request.cookies.get(CSRF, "")
    return {"token": existing if valid_csrf(existing, cookie) else issue_csrf(response, cookie)}


@router.post("/session", response_model=CsrfToken)
def exchange(body: Exchange, response: Response):
    app = firebase_app()
    try:
        claims = auth.verify_id_token(body.id_token, check_revoked=True, app=app)
        claims_actor(claims)
        if not -30 <= time.time() - claims.get("auth_time", 0) <= 300:
            raise HTTPException(401, "recent_sign_in")
        cookie = auth.create_session_cookie(body.id_token, expires_in=timedelta(hours=24), app=app)
    except (FirebaseError, ValueError):
        raise HTTPException(401, "sign_in") from None
    if isinstance(cookie, bytes):
        cookie = cookie.decode()
    response.set_cookie(SESSION, cookie, max_age=86400, **COOKIE)
    return {"token": issue_csrf(response, cookie)}


@router.post("/logout")
def logout(response: Response, request: Request):
    try:
        user: Actor = actor(request)
    except HTTPException:
        user = None
    if user:
        auth.revoke_refresh_tokens(user.uid, app=firebase_app())
    for name in (SESSION, CSRF):
        response.delete_cookie(name, **COOKIE)
    return {"ok": True}
