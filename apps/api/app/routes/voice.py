from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.integrations.speech import provider
from app.models import Form, JobDraft, Language
from app.routes.jobs import DB
from app.security import Actor, actor, rate_limit
from app.services.matching import can_read_job
from app.services.profiles import find_profile, require_role

router = APIRouter(prefix="/api/voice")


class Recording(Form):
    lang: Language
    wav: str = Field(min_length=40, max_length=1_333_336)


class Readback(Form):
    lang: Language
    job: UUID | None = None
    draft: JobDraft | None = None


@router.post("/transcribe")
def transcribe(body: Recording, user: Actor = Depends(actor)):
    rate_limit("stt", user.uid, 5)
    return provider.transcribe(body.wav, body.lang)


@router.post("/readback")
def readback(body: Readback, db: DB, user: Actor = Depends(actor)):
    rate_limit("tts", user.uid, 10)
    profile = find_profile(db, user)
    if not profile:
        raise HTTPException(403, "onboard_first")
    if bool(body.draft) == bool(body.job):
        raise HTTPException(422, "invalid_fields")
    if body.draft:
        require_role(profile, "employer")
        listing = body.draft.model_dump()
    else:
        listing = can_read_job(db, profile, body.job)
    return provider.speak(provider.summary(db, listing, body.lang), body.lang)
