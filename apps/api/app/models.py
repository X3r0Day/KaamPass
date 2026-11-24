from datetime import date, datetime, time
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["en", "hi"]
Role = Literal["worker", "employer"]
Kind = Literal["short_term", "permanent"]
Unit = Literal["shift", "day", "month", "job"]
State = Literal["open", "assigned", "completed", "filled", "cancelled"]
Key = Annotated[str, Field(min_length=1, max_length=80)]
Paise = Annotated[int, Field(ge=0, le=1_000_000_000, strict=True)]


def today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


class Form(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Place(BaseModel):
    id: str
    en: str
    hi: str
    pin: str


class Skill(BaseModel):
    id: str
    en: str
    hi: str
    aliases: str


class ProfileFields(Form):
    name: Key
    lang: Language
    area: Key
    skills: list[Key] = Field(default_factory=list, max_length=12)
    areas: list[Key] = Field(default_factory=list, max_length=3)
    kinds: list[Kind] = Field(default_factory=list, max_length=2)


class Onboarding(ProfileFields):
    role: Role


class Profile(Onboarding):
    public_id: str
    realm: Literal["member", "browser"] = "member"
    discoverable: bool
    discoverable_until: date | None


class Me(BaseModel):
    needs_onboarding: bool
    profile: Profile | None
    can_connect: bool = False


class Availability(Form):
    mode: Literal["paused", "today", "until", "ongoing"]
    until: date | None = None


class JobDraft(Form):
    skill: Key
    area: Key
    kind: Kind
    starts: date
    ends: date | None = None
    shift_time: time | None = None
    deadline: date
    pay: Paise
    unit: Unit
    title: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=1200)

    @model_validator(mode="after")
    def dates_and_rate(self):
        if not self.pay or self.deadline > self.starts:
            raise ValueError("pay or deadline")
        if self.kind == "permanent" and self.ends is not None:
            raise ValueError("permanent opening cannot end")
        if self.kind == "short_term" and (
            not self.ends or self.ends < self.starts or (self.starts == self.ends and not self.shift_time)
        ):
            raise ValueError("shift dates")
        return self


class Publish(JobDraft):
    submission_key: UUID
    share_contact: Literal[True]


class Job(JobDraft):
    id: UUID
    employer: str
    state: State
    created_at: datetime
    reason: Literal["locality", "postal", "chosen"] | None = None
    invitation_id: UUID | None = None
    invitation_status: str | None = None
    interested: bool = False
    selected: bool = False
    reported_pay: int | None = None


class Stats(BaseModel):
    jobs_posted: int = 0
    hired: int = 0
    completed: int = 0
    placements: int = 0
    earnings: int = 0


class Board(BaseModel):
    profile: Profile
    stats: Stats
    jobs: list[Job]
    more: bool


class Candidate(BaseModel):
    public_id: str
    name: str
    area: str
    invited: bool = False


class PersonRef(Form):
    worker: str = Field(pattern=r"^WKR-[1-9][0-9]{5}$")


class Consent(Form):
    share_contact: Literal[True]


class Answer(Form):
    accept: bool
    share_contact: bool = False


class Earnings(Form):
    pay: Paise
