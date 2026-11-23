from fastapi import HTTPException

from app.db.store import many, one, run
from app.models import today
from app.services.matching import PAGE, owned, worker_job
from app.services.profiles import require_role


def check_open(row):
    if not row:
        raise HTTPException(404, "not_found")
    if row["state"] != "open" or row["deadline"] < today():
        raise HTTPException(409, "opening_closed")


def invite(db, profile, job, worker):
    check_open(owned(db, profile, job, lock=True))
    run(db, "SELECT public_id FROM profiles WHERE public_id=:worker FOR UPDATE", worker=worker)
    if not worker_job(db, worker, job, visible=True):
        raise HTTPException(409, "not_available")
    run(
        db,
        """INSERT INTO invitations(job,worker) VALUES (:job,:worker)
               ON CONFLICT (job,worker) DO NOTHING""",
        job=job,
        worker=worker,
    )


def interest(db, profile, job):
    require_role(profile, "worker")
    params = dict(worker=profile.public_id, job=job)
    row = one(db, "SELECT state,deadline FROM jobs WHERE id=:job FOR UPDATE", **params)
    if one(db, "SELECT 1 FROM interests WHERE worker=:worker AND job=:job", **params):
        return
    check_open(row)
    if not worker_job(db, profile.public_id, job) and not one(
        db, "SELECT 1 FROM invitations WHERE job=:job AND worker=:worker AND response='pending'", **params
    ):
        raise HTTPException(404, "not_found")
    run(db, "INSERT INTO interests(job,worker) VALUES (:job,:worker) ON CONFLICT DO NOTHING", **params)
    run(
        db,
        "UPDATE invitations SET response='accepted' WHERE worker=:worker AND job=:job AND response='pending'",
        **params,
    )


def respond(db, profile, invitation, answer):
    require_role(profile, "worker")
    params = dict(id=invitation, worker=profile.public_id)
    row = one(db, "SELECT job,response FROM invitations WHERE id=:id AND worker=:worker", **params)
    if not row:
        raise HTTPException(404, "not_found")
    if answer.accept and not answer.share_contact:
        raise HTTPException(422, "consent")
    # Acquire the job lock before the invitation, the same order used by direct applications.
    run(db, "SELECT id FROM jobs WHERE id=:job FOR UPDATE", job=row["job"])
    row = one(db, "SELECT job,response FROM invitations WHERE id=:id AND worker=:worker FOR UPDATE", **params)
    target = "accepted" if answer.accept else "declined"
    if row["response"] == target:
        return
    if row["response"] != "pending":
        raise HTTPException(409, "changed")
    if answer.accept:
        interest(db, profile, row["job"])
    run(db, "UPDATE invitations SET response=:target WHERE id=:id", target=target, **params)


def interested_workers(db, profile, job, page):
    owned(db, profile, job)
    return many(
        db,
        """SELECT p.public_id,p.area FROM interests i JOIN profiles p ON p.public_id=i.worker
            WHERE i.job=:job ORDER BY i.consent_at,p.public_id LIMIT :size OFFSET :offset""",
        job=job,
        size=PAGE,
        offset=PAGE * page,
    )


def assign(db, profile, job, worker):
    listing = owned(db, profile, job, lock=True)
    params = dict(job=job, worker=worker)
    if listing["state"] == "assigned" and one(
        db, "SELECT 1 FROM assignments WHERE job=:job AND worker=:worker", **params
    ):
        return
    if listing["state"] != "open":
        raise HTTPException(409, "opening_closed")
    if not one(db, "SELECT 1 FROM interests WHERE job=:job AND worker=:worker", **params):
        raise HTTPException(409, "interest_required")
    run(db, "INSERT INTO assignments(job,worker) VALUES (:job,:worker)", **params)
    run(db, "UPDATE jobs SET state='assigned' WHERE id=:job", job=job)


def close(db, profile, job, target):
    listing = owned(db, profile, job, lock=True)
    if listing["state"] == target:
        return
    if target == "cancelled":
        allowed = listing["state"] in {"open", "assigned"}
    else:
        expected = "completed" if listing["kind"] == "short_term" else "filled"
        allowed = listing["state"] == "assigned" and expected == target
    if not allowed:
        raise HTTPException(409, "changed")
    run(db, "UPDATE jobs SET state=:target WHERE id=:job", job=job, target=target)


def contact(db, profile, job):
    partner = one(
        db,
        """SELECT p.phone,p.public_id,p.name FROM jobs j JOIN assignments a ON a.job=j.id
        JOIN profiles p ON p.public_id=CASE WHEN j.employer=:me THEN a.worker ELSE j.employer END
        WHERE j.id=:job AND j.state='assigned' AND :me IN (j.employer,a.worker)""",
        job=job,
        me=profile.public_id,
    )
    if not partner:
        raise HTTPException(404, "not_found")
    return partner


def earnings(db, profile, job, amount):
    require_role(profile, "worker")
    result = run(
        db,
        """UPDATE assignments a SET reported_pay=:amount FROM jobs j
        WHERE a.job=j.id AND j.id=:job AND a.worker=:me AND j.state='completed' AND j.kind='short_term'""",
        job=job,
        amount=amount,
        me=profile.public_id,
    )
    if not result.rowcount:
        raise HTTPException(404, "not_found")
