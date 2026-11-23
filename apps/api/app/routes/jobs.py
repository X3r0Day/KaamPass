from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection

from app.db.store import transaction
from app.models import Board, Candidate, Profile, Publish
from app.services import matching
from app.services.profiles import current_profile

router = APIRouter(prefix="/api")
DB = Annotated[Connection, Depends(transaction)]
Member = Annotated[Profile, Depends(current_profile)]
Page = Annotated[int, Query(ge=0, le=10000)]


@router.get("/me/dashboard", response_model=Board)
def board(
    profile: Member, db: DB, tab: Literal["matches", "invitations", "history"] = "matches", page: Page = 0
):
    return matching.dashboard(db, profile, tab, page)


@router.post("/jobs")
def publish(body: Publish, profile: Member, db: DB):
    return matching.publish(db, profile, body)


@router.get("/jobs/{job}/candidates", response_model=list[Candidate])
def candidates(job: UUID, profile: Member, db: DB, page: Page = 0):
    return matching.candidates(db, profile, job, page)
