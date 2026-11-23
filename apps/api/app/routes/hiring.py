from uuid import UUID
from fastapi import APIRouter
from app.models import Answer, Candidate, Consent, Earnings, PersonRef
from app.routes.jobs import DB, Member, Page
from app.services import hiring

router = APIRouter(prefix="/api")


@router.post("/jobs/{job}/invites")
def invite(job: UUID, body: PersonRef, profile: Member, db: DB):
    hiring.invite(db, profile, job, body.worker)
    return {"ok": True}


@router.post("/me/invitations/{invitation}/response")
def respond(invitation: UUID, body: Answer, profile: Member, db: DB):
    hiring.respond(db, profile, invitation, body)
    return {"ok": True}


@router.post("/jobs/{job}/interest")
def apply(job: UUID, body: Consent, profile: Member, db: DB):
    hiring.interest(db, profile, job)
    return {"ok": True}


@router.get("/jobs/{job}/interests", response_model=list[Candidate])
def interests(job: UUID, profile: Member, db: DB, page: Page = 0):
    return hiring.interested_workers(db, profile, job, page)


@router.post("/jobs/{job}/assign")
def assign(job: UUID, body: PersonRef, profile: Member, db: DB):
    hiring.assign(db, profile, job, body.worker)
    return {"ok": True}


@router.post("/jobs/{job}/complete")
def complete(job: UUID, profile: Member, db: DB):
    hiring.close(db, profile, job, "completed")
    return {"ok": True}


@router.post("/jobs/{job}/fill")
def fill(job: UUID, profile: Member, db: DB):
    hiring.close(db, profile, job, "filled")
    return {"ok": True}


@router.post("/jobs/{job}/cancel")
def cancel(job: UUID, profile: Member, db: DB):
    hiring.close(db, profile, job, "cancelled")
    return {"ok": True}


@router.get("/jobs/{job}/contact")
def contact(job: UUID, profile: Member, db: DB):
    return hiring.contact(db, profile, job)


@router.put("/jobs/{job}/earnings")
def earnings(job: UUID, body: Earnings, profile: Member, db: DB):
    hiring.earnings(db, profile, job, body.pay)
    return {"ok": True}
