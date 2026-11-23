from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db.store import engine
from app.routes import authentication
from app.security import protect_write
from app.settings import firebase_app, settings


@asynccontextmanager
async def lifespan(app):
    settings()
    engine()
    firebase_app()
    yield


app = FastAPI(title="KaamPaas", version="1.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(protect_write)])
app.include_router(authentication.router)


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    return JSONResponse({"detail": "invalid_fields", "fields": [e["loc"][-1] for e in exc.errors()]}, status_code=422)


@app.get("/api/health")
def health():
    return {"service": "kaampaas", "status": "ok"}
