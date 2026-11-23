from fastapi import APIRouter, Depends
from sqlalchemy import Connection

from app.db.store import many, transaction
from app.models import Availability, Me, Onboarding, Place, Profile, ProfileFields, Skill
from app.security import Actor, actor
from app.services import profiles
from app.services.profiles import current_profile

router = APIRouter(prefix="/api")


@router.get("/me", response_model=Me)
def me(user: Actor = Depends(actor), db: Connection = Depends(transaction)):
    profile = profiles.find_profile(db, user)
    return {"needs_onboarding": profile is None, "profile": profile}


@router.post("/me/onboarding", response_model=Profile)
def confirm(body: Onboarding, user: Actor = Depends(actor), db: Connection = Depends(transaction)):
    return profiles.register(db, user, body)


@router.patch("/me", response_model=Profile)
def save(
    body: ProfileFields,
    profile: Profile = Depends(current_profile),
    user: Actor = Depends(actor),
    db: Connection = Depends(transaction),
):
    profiles.edit(db, profile, body)
    return profiles.find_profile(db, user)


@router.put("/me/availability", response_model=Profile)
def available(
    body: Availability,
    profile: Profile = Depends(current_profile),
    user: Actor = Depends(actor),
    db: Connection = Depends(transaction),
):
    profiles.availability(db, profile, body)
    return profiles.find_profile(db, user)


@router.get("/skills", response_model=list[Skill])
def skills(db: Connection = Depends(transaction)):
    return many(db, "SELECT id,en,hi,aliases FROM skills ORDER BY en")


@router.get("/localities", response_model=list[Place])
def localities(db: Connection = Depends(transaction)):
    return many(db, "SELECT id,en,hi,pin FROM localities WHERE active ORDER BY en")
