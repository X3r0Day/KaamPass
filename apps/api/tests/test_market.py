from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.store import many, run
from app.models import Answer, Availability, Board, Onboarding, ProfileFields, Publish, today
from app.security import Actor
from app.services import hiring, matching, profiles

AREA = "201206-duhai"
OTHER = "201204-modi-nagar"


def member(db, role="worker", area=AREA, **fields):
    uid = uuid4().hex
    actor = Actor(uid, f"+1{int(uid[:12], 16) % 10**10:010}")
    form = Onboarding(
        role=role,
        name=f"Test {uid[:5]}",
        area=area,
        lang="hi",
        skills=["mason"] if role == "worker" else [],
        kinds=["short_term", "permanent"] if role == "worker" else [],
        **fields,
    )
    return profiles.register(db, actor, form), actor, form


def post(db, employer, kind="short_term", area=AREA, **changes):
    start = today() + timedelta(days=3)
    fields = dict(
        kind=kind,
        area=area,
        skill="mason",
        starts=start,
        ends=start if kind == "short_term" else None,
        deadline=today(),
        shift_time="08:00",
        pay=75000,
        unit="day" if kind == "short_term" else "month",
        submission_key=uuid4(),
        share_contact=True,
    )
    body = Publish(**(fields | changes))
    return matching.publish(db, employer, body)["id"], body


def test_confirmation_and_binding_do_not_duplicate(db, monkeypatch):
    w, user, form = member(db)
    assert profiles.register(db, user, form).public_id == w.public_id
    with pytest.raises(HTTPException, match="identity_conflict"):
        profiles.find_profile(db, Actor(uuid4().hex, user.phone))
    ids = iter([int(w.public_id[4:]) - 100000, (int(w.public_id[4:]) - 100000 + 1) % 900000])
    monkeypatch.setattr(profiles.secrets, "randbelow", lambda _: next(ids))
    other, _, _ = member(db)
    assert other.public_id != w.public_id
    with pytest.raises(HTTPException):
        profiles.edit(
            db,
            w,
            ProfileFields(
                name="Outside pilot", area="301001-alwar", lang="en", skills=["mason"], kinds=["permanent"]
            ),
        )


def test_pilot_ranking_and_deadlines(db):
    w, _, _ = member(db, areas=[OTHER])
    e, _, _ = member(db, "employer")
    local, _ = post(db, e)
    postal, _ = post(db, e, area="201206-abupur")
    chosen, _ = post(db, e, area=OTHER)
    post(db, e, skill="plumber")
    post(db, e, area="201012-kaushambi")
    expired, _ = post(db, e)
    run(db, "UPDATE jobs SET deadline=:day WHERE id=:id", day=today() - timedelta(days=1), id=expired)
    result = Board(**matching.dashboard(db, w, "matches", 0))
    assert [(j.id, j.reason) for j in result.jobs] == [
        (local, "locality"),
        (postal, "postal"),
        (chosen, "chosen"),
    ]
    assert len(many(db, "SELECT id FROM localities WHERE active AND state='Uttar Pradesh'")) == 21


def test_hiring_visibility_contact_and_income(db):
    w, _, _ = member(db)
    e, _, _ = member(db, "employer")
    outsider, _, _ = member(db, "employer")
    job, form = post(db, e)
    assert matching.publish(db, e, form)["id"] == job
    with pytest.raises(HTTPException, match="submission_conflict"):
        matching.publish(db, e, form.model_copy(update={"pay": 40000}))
    assert matching.candidates(db, e, job, 0) == []
    profiles.availability(db, w, Availability(mode="today"))
    assert matching.candidates(db, e, job, 0)[0]["public_id"] == w.public_id
    profiles.availability(db, w, Availability(mode="paused"))
    with pytest.raises(HTTPException, match="not_available"):
        hiring.invite(db, e, job, w.public_id)
    profiles.availability(db, w, Availability(mode="ongoing"))
    hiring.invite(db, e, job, w.public_id)
    invitation = matching.dashboard(db, w, "invitations", 0)["jobs"][0]["invitation_id"]
    hiring.respond(db, w, invitation, Answer(accept=True, share_contact=True))
    with pytest.raises(HTTPException):
        hiring.contact(db, e, job)
    hiring.assign(db, e, job, w.public_id)
    assert hiring.contact(db, w, job)["public_id"] == e.public_id
    with pytest.raises(HTTPException):
        hiring.contact(db, outsider, job)
    with pytest.raises(HTTPException):
        hiring.close(db, outsider, job, "completed")
    hiring.close(db, e, job, "completed")
    with pytest.raises(HTTPException):
        hiring.contact(db, w, job)
    hiring.earnings(db, w, job, 65500)
    permanent, _ = post(db, e, "permanent")
    hiring.interest(db, w, permanent)
    hiring.assign(db, e, permanent, w.public_id)
    with pytest.raises(HTTPException):
        hiring.close(db, e, permanent, "completed")
    hiring.close(db, e, permanent, "filled")
    with pytest.raises(HTTPException):
        hiring.earnings(db, w, permanent, 2000000)
    stats = Board(**matching.dashboard(db, w, "history", 0)).stats
    assert (stats.completed, stats.placements, stats.earnings) == (1, 1, 65500)


def test_expired_visibility(db):
    w, _, _ = member(db)
    e, _, _ = member(db, "employer")
    job, _ = post(db, e)
    run(
        db,
        "UPDATE profiles SET discoverable=true,discoverable_until=:end WHERE public_id=:me",
        end=today() - timedelta(days=1),
        me=w.public_id,
    )
    assert matching.candidates(db, e, job, 0) == []
    assert matching.dashboard(db, w, "matches", 0)["jobs"]


def test_competing_assignments_choose_only_one(database):
    with database.begin() as db:
        e, _, _ = member(db, "employer")
        first, _, _ = member(db)
        second, _, _ = member(db)
        job, _ = post(db, e)
        for w in (first, second):
            hiring.interest(db, w, job)
    gate = Barrier(2)

    def try_assign(w):
        with database.begin() as db:
            gate.wait(timeout=5)
            try:
                hiring.assign(db, e, job, w.public_id)
            except HTTPException as exc:
                return exc.status_code
            return 200

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(try_assign, [first, second])) == [200, 409]
