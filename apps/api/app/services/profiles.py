import secrets

from fastapi import Depends, HTTPException
from sqlalchemy import Connection

from app.db.store import many, one, run, transaction
from app.models import Availability, Onboarding, Profile, ProfileFields, today
from app.security import Actor, actor

PUBLIC_FIELDS = """p.public_id,p.name,p.role,p.lang,p.area,p.kinds,
    (p.discoverable AND (p.discoverable_until IS NULL OR p.discoverable_until>=:today)) AS discoverable,
    p.discoverable_until,ARRAY(SELECT skill FROM worker_skills WHERE worker=p.public_id ORDER BY skill) AS skills,
    ARRAY(SELECT area FROM worker_work_areas WHERE worker=p.public_id ORDER BY area) AS areas"""


def find_profile(db, user: Actor) -> Profile | None:
    bindings = many(
        db,
        """SELECT phone,subject FROM identity_bindings WHERE provider=:provider
                       AND (phone=:phone OR subject=:uid)""",
        phone=user.phone,
        uid=user.uid,
        provider=user.provider,
    )
    if any(b["phone"] != user.phone or b["subject"] != user.uid for b in bindings):
        raise HTTPException(409, "identity_conflict")
    if not bindings:
        return None
    row = one(
        db, f"SELECT {PUBLIC_FIELDS} FROM profiles p WHERE p.phone=:phone", phone=user.phone, today=today()
    )
    return Profile(**row)


def reuse_confirmed_profile(db, user: Actor):
    """Link a second, independently verified channel without creating or editing a profile."""
    run(db, "SELECT pg_advisory_xact_lock(hashtextextended(:phone,0))", phone=user.phone)
    current = find_profile(db, user)
    if current:
        return current
    if not one(db, "SELECT 1 FROM profiles WHERE phone=:phone", phone=user.phone):
        raise HTTPException(404, "not_found")
    bind(db, user)
    return find_profile(db, user)


def bind(db, user: Actor):
    run(
        db,
        "INSERT INTO identity_bindings VALUES (:provider,:uid,:phone)",
        provider=user.provider,
        uid=user.uid,
        phone=user.phone,
    )


def current_profile(user: Actor = Depends(actor), db: Connection = Depends(transaction)) -> Profile:
    profile = find_profile(db, user)
    if not profile:
        raise HTTPException(403, "onboard_first")
    return profile


def require_role(profile: Profile, role: str):
    if profile.role != role:
        raise HTTPException(403, "wrong_role")


def validate_choices(db, fields: ProfileFields, role):
    if role == "worker":
        if not fields.skills or not fields.kinds:
            raise HTTPException(422, "choose_trade_type")
    elif fields.skills or fields.kinds or fields.areas:
        raise HTTPException(422, "invalid_fields")
    areas = set([fields.area, *fields.areas])
    if len(areas) != 1 + len(fields.areas) or len(set(fields.skills)) != len(fields.skills):
        raise HTTPException(422, "invalid_fields")
    places = many(db, "SELECT id FROM localities WHERE active AND id=ANY(:ids)", ids=list(areas))
    skills = many(db, "SELECT id FROM skills WHERE id=ANY(:ids)", ids=fields.skills)
    if len(places) != len(areas) or len(skills) != len(fields.skills):
        raise HTTPException(422, "invalid_fields")


def replace_choices(db, pid: str, fields: ProfileFields):
    run(db, "DELETE FROM worker_skills WHERE worker=:id", id=pid)
    run(db, "DELETE FROM worker_work_areas WHERE worker=:id", id=pid)
    for skill in fields.skills:
        run(db, "INSERT INTO worker_skills VALUES (:id,:skill)", id=pid, skill=skill)
    for area in fields.areas:
        run(db, "INSERT INTO worker_work_areas VALUES (:id,:area)", id=pid, area=area)


def register(db, user: Actor, fields: Onboarding):
    for key in (user.phone, f"{user.provider}:{user.uid}"):
        run(db, "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))", key=key)
    existing = find_profile(db, user)
    if existing:
        if existing.role != fields.role:
            raise HTTPException(409, "identity_conflict")
        return existing
    if one(db, "SELECT 1 FROM profiles WHERE phone=:phone", phone=user.phone):
        raise HTTPException(409, "identity_conflict")
    validate_choices(db, fields, fields.role)
    for _ in range(12):
        prefix = "WKR" if fields.role == "worker" else "EMP"
        pid = f"{prefix}-{secrets.randbelow(900000) + 100000}"
        row = one(
            db,
            """INSERT INTO profiles(phone,public_id,role,name,lang,area,kinds)
             VALUES (:phone,:id,:role,:name,:lang,:area,:kinds)
             ON CONFLICT (public_id) DO NOTHING RETURNING public_id""",
            phone=user.phone,
            id=pid,
            **fields.model_dump(),
        )
        if row:
            break
    else:
        raise HTTPException(503, "retry")
    bind(db, user)
    replace_choices(db, pid, fields)
    return find_profile(db, user)


def edit(db, profile: Profile, fields: ProfileFields):
    validate_choices(db, fields, profile.role)
    run(
        db,
        "UPDATE profiles SET name=:name,lang=:lang,area=:area,kinds=:kinds WHERE public_id=:id",
        id=profile.public_id,
        **fields.model_dump(),
    )
    replace_choices(db, profile.public_id, fields)


def availability(db, profile: Profile, body: Availability):
    require_role(profile, "worker")
    end = today() if body.mode == "today" else body.until if body.mode == "until" else None
    if body.mode == "until" and (not end or end < today()):
        raise HTTPException(422, "invalid_fields")
    run(
        db,
        "UPDATE profiles SET discoverable=:visible,discoverable_until=:end WHERE public_id=:id",
        visible=body.mode != "paused",
        end=end,
        id=profile.public_id,
    )
