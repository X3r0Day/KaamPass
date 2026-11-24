from hashlib import sha256

from fastapi import HTTPException

from app.db.store import many, one
from app.models import Profile, Publish, today
from app.services.profiles import require_role

COLUMNS = """j.id,j.employer,j.skill,j.area,j.kind,j.starts,j.ends,j.shift_time,j.deadline,
             j.pay,j.unit,j.title,j.description,j.state,j.created_at"""
MATCH = """FROM profiles w JOIN worker_skills ws ON ws.worker=w.public_id
    JOIN jobs j ON j.skill=ws.skill AND j.kind=ANY(w.kinds)
    JOIN profiles employer_profile ON employer_profile.public_id=j.employer AND employer_profile.realm=w.realm
    JOIN localities home ON home.id=w.area JOIN localities site ON site.id=j.area
    LEFT JOIN worker_work_areas extra ON extra.worker=w.public_id AND extra.area=j.area"""
ELIGIBLE = """j.state='open' AND site.active AND j.deadline>=:today AND w.role='worker'
    AND (home.pin=site.pin OR extra.area IS NOT NULL)"""
VISIBLE = "w.discoverable AND (w.discoverable_until IS NULL OR w.discoverable_until>=:today)"
TIER = "CASE WHEN home.id=site.id THEN 1 WHEN home.pin=site.pin THEN 2 ELSE 3 END"
REASON = "CASE WHEN home.id=site.id THEN 'locality' WHEN home.pin=site.pin THEN 'postal' ELSE 'chosen' END"
RELATIONS = """LEFT JOIN invitations v ON v.job=j.id AND v.worker=:me
    LEFT JOIN interests i ON i.job=j.id AND i.worker=:me
    LEFT JOIN assignments a ON a.job=j.id AND a.worker=:me"""
FLAGS = """v.id AS invitation_id,v.response AS invitation_status,i.worker IS NOT NULL AS interested,
           a.worker IS NOT NULL AS selected,a.reported_pay"""
PAGE = 12


def publish(db, profile: Profile, form: Publish):
    require_role(profile, "employer")
    fields = form.model_dump()
    digest = sha256(form.model_dump_json().encode()).hexdigest()
    params = dict(fields, employer=profile.public_id, digest=digest)
    existing = one(
        db, "SELECT id,digest FROM jobs WHERE employer=:employer AND submission_key=:submission_key", **params
    )
    if not existing:
        if form.deadline < today():
            raise HTTPException(422, "deadline_passed")
        trade = one(db, "SELECT hi,en FROM skills WHERE id=:skill", **fields)
        if not trade or not one(db, "SELECT id FROM localities WHERE active AND id=:area", **fields):
            raise HTTPException(422, "invalid_fields")
        params["title"] = form.title or trade[profile.lang]
        existing = one(
            db,
            """INSERT INTO jobs(employer,submission_key,digest,skill,area,kind,title,description,
              starts,ends,shift_time,deadline,pay,unit) VALUES (:employer,:submission_key,:digest,:skill,:area,:kind,
              :title,:description,:starts,:ends,:shift_time,:deadline,:pay,:unit)
              ON CONFLICT(employer,submission_key) DO UPDATE SET digest=jobs.digest RETURNING id,digest""",
            **params,
        )
    if existing["digest"] != digest:
        raise HTTPException(409, "submission_conflict")
    return {"id": existing["id"]}


def worker_job(db, worker, job, visible=False):
    constraints = f" AND {VISIBLE}" if visible else ""
    return one(
        db,
        f"SELECT j.id {MATCH} WHERE {ELIGIBLE}{constraints} AND w.public_id=:worker AND j.id=:job",
        worker=worker,
        job=job,
        today=today(),
    )


def can_read_job(db, profile, job):
    row = one(
        db,
        f"""SELECT {COLUMNS} FROM jobs j {RELATIONS}
        WHERE j.id=:job AND (j.employer=:me OR v.id IS NOT NULL OR i.worker IS NOT NULL)""",
        job=job,
        me=profile.public_id,
    )
    if row:
        return row
    if profile.role == "worker" and worker_job(db, profile.public_id, job):
        return one(db, f"SELECT {COLUMNS} FROM jobs j WHERE j.id=:job", job=job)
    raise HTTPException(404, "not_found")


def dashboard(db, profile: Profile, tab: str, page: int, *, area=None, skill=None, kind=None):
    params = dict(me=profile.public_id, today=today(), size=PAGE + 1, offset=page * PAGE)
    order = "j.created_at DESC,j.id"
    if profile.role == "employer":
        query = f"SELECT {COLUMNS} FROM jobs j WHERE j.employer=:me"
        stats = one(
            db,
            """SELECT count(*) AS jobs_posted,count(distinct a.worker) FILTER (WHERE j.state<>'cancelled') AS hired,
            count(*) FILTER (WHERE j.state='completed') AS completed,count(*) FILTER (WHERE j.state='filled') AS placements
            FROM jobs j LEFT JOIN assignments a ON a.job=j.id WHERE j.employer=:me""",
            **params,
        )
    else:
        if tab == "matches":
            query = f"SELECT {COLUMNS},{FLAGS},{REASON} AS reason {MATCH} {RELATIONS} WHERE {ELIGIBLE} AND w.public_id=:me"
            order = TIER + "," + order
        else:
            condition = "v.id IS NOT NULL" if tab == "invitations" else "i.worker IS NOT NULL"
            query = f"SELECT {COLUMNS},{FLAGS} FROM jobs j {RELATIONS} WHERE {condition}"
        stats = one(
            db,
            """SELECT count(*) FILTER (WHERE j.state='completed') AS completed,
             count(*) FILTER (WHERE j.state='filled') AS placements,
             coalesce(sum(a.reported_pay) FILTER (WHERE j.state='completed'),0) AS earnings
             FROM assignments a JOIN jobs j ON j.id=a.job WHERE a.worker=:me""",
            **params,
        )
    for field, value in (("area", area), ("skill", skill), ("kind", kind)):
        if value is not None:
            query += f" AND j.{field}=:{field}"
            params[field] = value
    jobs = many(db, query + f" ORDER BY {order} LIMIT :size OFFSET :offset", **params)
    return {"profile": profile, "stats": stats, "jobs": jobs[:PAGE], "more": len(jobs) > PAGE}


def owned(db, profile, job, lock=False):
    require_role(profile, "employer")
    row = one(
        db,
        "SELECT id,state,kind,deadline FROM jobs WHERE id=:job AND employer=:me"
        + (" FOR UPDATE" if lock else ""),
        job=job,
        me=profile.public_id,
    )
    if not row:
        raise HTTPException(404, "not_found")
    return row


def candidates(db, profile, job, page):
    owned(db, profile, job)
    return many(
        db,
        f"""SELECT w.public_id,w.area,EXISTS(SELECT 1 FROM invitations v WHERE v.worker=w.public_id
         AND v.job=j.id) AS invited {MATCH} WHERE j.id=:job AND {ELIGIBLE} AND {VISIBLE}
         ORDER BY {TIER},w.public_id LIMIT :size OFFSET :offset""",
        job=job,
        today=today(),
        size=PAGE,
        offset=page * PAGE,
    )
