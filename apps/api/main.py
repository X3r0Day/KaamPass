from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db.store import engine
from app.integrations.whatsapp import meta
from app.routes import authentication, hiring, jobs, profiles, voice, whatsapp
from app.security import protect_write
from app.settings import firebase_app, settings


@asynccontextmanager
async def lifespan(app):
    config = settings()
    engine()
    meta.config()
    if config.phone_auth_enabled:
        firebase_app()
    yield


app = FastAPI(
    title="KaamPaas",
    version="1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    dependencies=[Depends(protect_write)],
)
app.include_router(authentication.router)
app.include_router(profiles.router)
app.include_router(jobs.router)
app.include_router(hiring.router)
app.include_router(voice.router)
app.include_router(whatsapp.router)


@app.middleware("http")
async def private_responses(request: Request, call_next):
    length = request.headers.get("content-length", "")
    cap = {"/api/voice/transcribe": 1_400_000, "/api/whatsapp/webhook": 262_144}.get(request.url.path, 32_768)
    if length and (not length.isascii() or not length.isdecimal() or len(length) > 10 or int(length) > cap):
        response = JSONResponse({"detail": "body_too_large"}, status_code=413)
    else:
        response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    return JSONResponse(
        {"detail": "invalid_fields", "fields": [e["loc"][-1] for e in exc.errors()]}, status_code=422
    )


@app.get("/api/health")
def health():
    return {"service": "kaampaas", "status": "ok"}
