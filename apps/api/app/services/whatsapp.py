import re
from dataclasses import dataclass
from secrets import token_urlsafe
from uuid import UUID

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.db.store import many, one, run
from app.integrations.speech import provider
from app.integrations.whatsapp import assistant, meta
from app.models import Availability, Onboarding
from app.security import Actor, rate_limit
from app.services import hiring, matching, profiles, whatsapp_post


@dataclass
class Incoming:
    id: str
    phone: str
    kind: str
    text: str = ""
    button: str = ""
    media: str = ""


def text(body):
    return {"type": "text", "text": {"body": body[:4000], "preview_url": False}}


def buttons(body, choices):
    return {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [{"type": "reply", "reply": {"id": key, "title": name}} for key, name in choices]
            },
        },
    }


def normalize(value):
    return " ".join(value.casefold().strip(" .,;:!?।").replace("-", " ").split())


def dictionaries(db):
    return {
        "areas": many(db, "SELECT id,en,hi,pin FROM localities WHERE active ORDER BY en"),
        "skills": many(db, "SELECT id,en,hi,aliases FROM skills ORDER BY en"),
    }


def options(key, values):
    items = values[key]
    return {r["id"]: r for r in items}


def names(row):
    return [row["id"], row["en"], row["hi"], *row.get("aliases", "").split("|")]


def area_id(source, catalog):
    key = normalize(source)
    rows = [p for p in catalog["areas"] if key in {normalize(k) for k in [*names(p), p["pin"]]}]
    return rows[0]["id"] if len(rows) == 1 else None


def skills_from(source, catalog):
    said = [normalize(x) for x in source.replace(" और ", ",").replace(" and ", ",").split(",")]
    return [s["id"] for s in catalog["skills"] if any(x and x in said for x in map(normalize, names(s)))]


def kinds_from(source):
    normalized = normalize(source)
    if normalized in {"both", "दोनों", "all"}:
        return ["short_term", "permanent"]
    if normalized in {
        "short term",
        "short_term",
        "daily",
        "shift",
        "temporary",
        "अस्थायी",
        "दिहाड़ी",
        "अस्थायी काम",
    }:
        return ["short_term"]
    if normalized in {"permanent", "permanent job", "स्थायी", "स्थायी नौकरी"}:
        return ["permanent"]
    return []


def handwritten(source, expected, catalog):
    updates = {}
    labels = {
        "name": "name",
        "नाम": "name",
        "language": "lang",
        "lang": "lang",
        "भाषा": "lang",
        "role": "role",
        "भूमिका": "role",
        "area": "area",
        "locality": "area",
        "इलाका": "area",
        "trade": "skills",
        "trades": "skills",
        "skill": "skills",
        "skills": "skills",
        "हुनर": "skills",
        "type": "kinds",
        "work": "kinds",
        "प्रकार": "kinds",
    }
    pieces = [line.strip() for line in source.splitlines() if line.strip()]
    for part in pieces:
        label, sep, right = part.partition(":")
        field = labels.get(normalize(label)) if sep else expected if len(pieces) == 1 else None
        value = right.strip() if sep else part
        simple = normalize(value)
        if (
            field == "name"
            and 1 <= len(value) <= 80
            and not any(c in value for c in "@\n\r")
            and (
                sep
                or (
                    len(value.split()) <= 6
                    and not any(word in f" {simple} " for word in (" from ", " and ", " से ", " और "))
                )
            )
        ):
            updates["name"] = value
        elif field == "role":
            if simple in {"worker", "work", "कामगार", "काम चाहिए", "मज़दूर"}:
                updates["role"] = "worker"
            elif simple in {"employer", "hire", "नियोक्ता", "काम देना है", "मालिक"}:
                updates["role"] = "employer"
        elif field == "lang" and simple in {"hindi", "हिंदी", "हिन्दी", "hi", "english", "अंग्रेज़ी", "en"}:
            updates["lang"] = "hi" if simple in {"hindi", "हिंदी", "हिन्दी", "hi"} else "en"
        elif field == "area" and (area := area_id(value, catalog)):
            updates["area"] = area
        elif field == "skills" and (skills := skills_from(value, catalog)):
            updates["skills"] = skills
        elif field == "kinds" and (kinds := kinds_from(value)):
            updates["kinds"] = kinds
    return updates


def merge(draft, updates, catalog):
    for key, value in updates.items():
        if key == "role" and value in ("worker", "employer"):
            draft[key] = value
        elif key == "lang" and value in ("en", "hi"):
            draft[key] = value
        elif key == "name" and isinstance(value, str):
            value = " ".join(value.split())
            if 1 <= len(value) <= 80 and "@" not in value and sum(c.isdecimal() for c in value) < 8:
                draft[key] = value
        elif key == "area" and value in options("areas", catalog):
            draft[key] = value
        elif key in {"skills", "kinds"} and isinstance(value, list):
            allowed = options("skills", catalog) if key == "skills" else {"short_term", "permanent"}
            cleaned = list(dict.fromkeys(v for v in value if v in allowed))
            if cleaned:
                draft[key] = cleaned


def say(lang, en, hi):
    return hi if lang == "hi" else en


def prompt(draft, lang, cat):
    keys = ["role", "name", "area"] + (["skills", "kinds"] if draft.get("role") == "worker" else [])
    field = next((key for key in keys if not draft.get(key)), None)
    if field == "role":
        return field, buttons(
            say(lang, "Do you want to find work or hire someone?", "काम चाहिए या किसी को काम देना है?"),
            [
                ("role:worker", say(lang, "Find work", "काम खोजें")),
                ("role:employer", say(lang, "Hire", "काम दें")),
            ],
        )
    if field == "name":
        return field, text(
            say(
                lang,
                "What name should we display? Type your name or business name.",
                "कौन-सा नाम दिखाएँ? अपना या दुकान का नाम लिखें।",
            )
        )
    if field == "area":
        areas = ", ".join(f"{p[lang]} ({p['pin']})" for p in cat["areas"])
        return field, text(
            say(
                lang,
                "Which Ghaziabad work area? Reply with one locality name from this list:\n",
                "गाज़ियाबाद में काम का इलाका कौन-सा है? सूची से एक इलाका लिखें:\n",
            )
            + areas
        )
    if field == "skills":
        trades = ", ".join(k[lang] for k in cat["skills"])
        return field, text(
            say(
                lang,
                "Which trade? Choose one or more, separated by commas:\n",
                "कौन-सा हुनर है? सूची से एक या अधिक लिखें, अल्पविराम लगाएँ:\n",
            )
            + trades
        )
    if field == "kinds":
        return field, buttons(
            say(lang, "What type of work do you want?", "आपको कैसा काम चाहिए?"),
            [
                ("kind:short_term", say(lang, "Short-term", "अस्थायी")),
                ("kind:permanent", say(lang, "Permanent", "स्थायी")),
                ("kind:both", say(lang, "Both", "दोनों")),
            ],
        )
    return None, None


def onboarding_summary(draft, lang, cat):
    place = options("areas", cat)[draft["area"]]
    role = say(lang, "Worker", "कामगार") if draft["role"] == "worker" else say(lang, "Employer", "नियोक्ता")
    details = [
        say(lang, "Review your KaamPaas profile", "अपनी KaamPaas प्रोफ़ाइल जाँचें"),
        f"{say(lang, 'Name', 'नाम')}: {draft['name']}",
        f"{say(lang, 'Role', 'भूमिका')}: {role}",
        f"{say(lang, 'Work area', 'इलाका')}: {place[lang]} ({place['pin']})",
    ]
    if draft["role"] == "worker":
        details.append(
            f"{say(lang, 'Trades', 'हुनर')}: "
            + ", ".join(options("skills", cat)[s][lang] for s in draft["skills"])
        )
        details.append(
            f"{say(lang, 'Opening types', 'काम के प्रकार')}: "
            + ", ".join(
                say(lang, "Short-term", "अस्थायी") if k == "short_term" else say(lang, "Permanent", "स्थायी")
                for k in draft["kinds"]
            )
        )
    details.append(
        say(
            lang,
            "Tap Yes to register. Your number is not shown in the work board.",
            "पंजीकरण के लिए हाँ दबाएँ। आपका नंबर काम की सूची में नहीं दिखेगा।",
        )
    )
    return "\n".join(details)


def save(db, phone, state):
    run(
        db,
        """INSERT INTO whatsapp_conversations(phone,draft,lang,assisted,pending,expected,lookup)
                 VALUES (:phone,:draft,:lang,:assisted,:pending,:expected,:lookup) ON CONFLICT (phone) DO UPDATE
                 SET draft=excluded.draft,lang=excluded.lang,assisted=excluded.assisted,pending=excluded.pending,
                     expected=excluded.expected,lookup=excluded.lookup,updated_at=now()""",
        phone=phone,
        draft=Jsonb(state["draft"]),
        lang=state["lang"],
        assisted=state["assisted"],
        pending=state["pending"],
        expected=state["expected"],
        lookup=Jsonb(state["lookup"]),
    )


def consent_message(lang):
    return buttons(
        say(
            lang,
            "KaamPaas • Ghaziabad. Choose how to continue. With voice + AI, Google transcribes voice notes and "
            "Token Harbor/DeepSeek processes the text you provide. Free-model data may be shared under its terms. "
            "Don't send IDs, addresses or financial details. Guided text sends nothing to those AI services.",
            "KaamPaas • गाज़ियाबाद। आवाज़ + AI में Google आवाज़ लिखता है और Token Harbor/DeepSeek दिए गए शब्द पढ़ता है। "
            "मुफ़्त मॉडल की शर्तों के अनुसार डेटा साझा हो सकता है। पहचान पत्र, पता या बैंक विवरण न भेजें। बिना AI के लिखकर भी जारी रख सकते हैं।",
        ),
        [
            ("mode:ai", say(lang, "Voice + AI", "आवाज़ + AI")),
            ("mode:text", say(lang, "Guided text", "लिखकर जारी रखें")),
            ("lang:en" if lang == "hi" else "lang:hi", "English" if lang == "hi" else "हिन्दी"),
        ],
    )


def show_menu(lang, worker=True):
    return text(
        say(
            lang,
            "Try: nearby jobs, invitations, applications, my profile, or availability."
            if worker
            else "Try: post a job, my postings, my profile, or help.",
            "लिखें: पास का काम, निमंत्रण, आवेदन, मेरी प्रोफ़ाइल या उपलब्धता।"
            if worker
            else "लिखें: काम पोस्ट करें, मेरे पोस्ट, मेरी प्रोफ़ाइल या मदद।",
        )
    )


def query_from(text_in):
    n = normalize(text_in)
    for intent, words in {
        "matches": {"jobs", "nearby jobs", "find work", "पास का काम", "आस पास के काम", "नौकरी"},
        "invitations": {"invitations", "invites", "निमंत्रण"},
        "history": {"applications", "history", "आवेदन"},
        "posted": {"my postings", "my jobs", "postings", "मेरे पोस्ट"},
        "profile": {"my profile", "profile", "मेरी प्रोफ़ाइल"},
        "availability": {"availability", "उपलब्धता"},
        "help": {"help", "menu", "मदद", "मेनू"},
    }.items():
        if n in words:
            return assistant.Query(intent=intent)
    return None


def nearby_fallback(source, catalog, role):
    if role != "worker":
        return None
    phrase = normalize(source)
    if not re.search(
        r"\b(jobs?|shifts?|vacanc(?:y|ies)|openings?)\b|पास का काम|पास में काम|नौकरी|दिहाड़ी", phrase
    ):
        return None

    def mentioned(row):
        return any(
            n and re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", phrase) for n in map(normalize, names(row))
        )

    areas = [row["id"] for row in catalog["areas"] if mentioned(row)]
    trades = [row["id"] for row in catalog["skills"] if mentioned(row)]
    kind = (
        "short_term"
        if any(x in phrase for x in ("short term", "दिहाड़ी", "अस्थायी", "day shift"))
        else "permanent"
        if any(x in phrase for x in ("permanent", "स्थायी"))
        else None
    )
    return assistant.Query(
        intent="matches",
        kind=kind,
        area=areas[0] if len(areas) == 1 else None,
        skill=trades[0] if len(trades) == 1 else None,
    )


def list_for(db, profile, query, lang, catalog, state, phone):
    intent = query.intent
    if intent == "help":
        return show_menu(lang, profile.role == "worker")
    if intent == "profile":
        p = options("areas", catalog).get(profile.area, {})
        return text(f"{profile.name}\n{profile.public_id}\n{p.get(lang, profile.area)}")
    if intent == "availability" and profile.role == "worker":
        title = (
            say(lang, "Open to hirers", "काम के लिए उपलब्ध")
            if profile.discoverable
            else say(lang, "Paused", "अभी उपलब्ध नहीं")
        )
        return buttons(
            title,
            [
                ("availability:today", say(lang, "Open today", "आज उपलब्ध")),
                ("availability:paused", say(lang, "Pause", "रोकें")),
            ],
        )
    allowed = {"worker": {"matches", "invitations", "history"}, "employer": {"posted"}}
    if intent not in allowed[profile.role]:
        return show_menu(lang, profile.role == "worker")
    area = query.area if query.area in options("areas", catalog) else None
    skill = query.skill if query.skill in options("skills", catalog) else None
    jobs = matching.dashboard(db, profile, intent, 0, area=area, skill=skill, kind=query.kind)["jobs"][:5]
    state.update(
        lookup={"jobs": [str(j["id"]) for j in jobs] if intent == "matches" else []},
        expected=None,
        pending=None,
    )
    save(db, phone, state)
    if not jobs:
        return text(
            say(
                lang,
                "No openings match this request. Try “nearby jobs” without a filter.",
                "इस खोज में कोई काम नहीं मिला। बिना फ़िल्टर के “पास का काम” लिखें।",
            )
        )
    lines = [say(lang, "KaamPaas openings", "KaamPaas के काम")]
    areas, skills = options("areas", catalog), options("skills", catalog)
    for i, j in enumerate(jobs, start=1):
        place = areas.get(j["area"])
        title = skills.get(j["skill"], {}).get(lang, j["title"])
        units = {"day": "दिन", "month": "महीना", "job": "काम", "shift": "पाली"}
        states = {
            "open": "खुला",
            "assigned": "सौंपा गया",
            "completed": "पूरा",
            "filled": "नियुक्ति हुई",
            "cancelled": "रद्द",
        }
        area_label = f"{place[lang]} ({place['pin']})" if place else j["area"]
        kind = (
            say(lang, "Permanent", "स्थायी") if j["kind"] == "permanent" else say(lang, "Short-term", "अस्थायी")
        )
        unit = units[j["unit"]] if lang == "hi" else j["unit"]
        state = states[j["state"]] if lang == "hi" else j["state"]
        amount = f"{j['pay'] / 100:,.2f}".rstrip("0").rstrip(".")
        description = f"\n{j['description'][:130]}" if j["description"] else ""
        lines.append(
            f"{i}. {title} · {kind} · {state}\n{area_label}\n₹{amount}/{unit} • {j['starts'].strftime('%d/%m/%Y')}{description}"
        )
    if intent == "matches":
        lines.append(
            say(
                lang,
                "To express interest, type “apply 1” (or the number of another listing).",
                "रुचि दिखाने के लिए “आवेदन 1” लिखें, या सूची का दूसरा नंबर दें।",
            )
        )
    return text("\n\n".join(lines))


def application(db, profile, user, state, lang, cmd, source):
    if profile.role != "worker":
        return None
    if cmd.startswith("apply:"):
        if state["expected"] != "apply" or cmd != "apply:" + (state["pending"] or "!"):
            return text(
                say(
                    lang,
                    "That confirmation expired. Search nearby jobs again.",
                    "पुष्टि समाप्त हुई। पास का काम फिर खोजें।",
                )
            )
        job = UUID(state["lookup"]["chosen"])
        state["lookup"].pop("chosen", None)
        state.update(expected=None, pending=None)
        save(db, user.phone, state)
        try:
            hiring.interest(db, profile, job)
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            return text(
                say(
                    lang,
                    "This opening is no longer accepting applications from you.",
                    "इस काम के लिए अब आप आवेदन नहीं कर सकते।",
                )
            )
        return text(
            say(
                lang,
                "Interest sent. Your phone is shared only if the employer assigns you.",
                "रुचि भेजी गई। नियोक्ता के चुनने पर ही आपका नंबर साझा होगा।",
            )
        )
    parts = normalize(source).split()
    if len(parts) == 2 and parts[0] in {"apply", "आवेदन"} and parts[1].isdecimal() and len(parts[1]) == 1:
        n = int(parts[1])
        jobs = state["lookup"].get("jobs", [])
        if not 1 <= n <= len(jobs) or not matching.worker_job(db, profile.public_id, UUID(jobs[n - 1])):
            return text(
                say(
                    lang,
                    "Send “nearby jobs” first, then use a number from the current list.",
                    "पहले “पास का काम” भेजें, फिर नई सूची में दिया नंबर चुनें।",
                )
            )
        state["lookup"]["chosen"] = jobs[n - 1]
        state.update(expected="apply", pending=token_urlsafe(16))
        save(db, user.phone, state)
        return buttons(
            say(
                lang,
                f"Express interest in listing {n}? The employer can see your number only after assigning you.",
                f"क्या आप काम {n} में रुचि रखते हैं? काम सौंपने के बाद ही नियोक्ता आपका नंबर देख पाएगा।",
            ),
            [("apply:" + state["pending"], say(lang, "Send interest", "रुचि भेजें"))],
        )
    return None


def handle(db, message: Incoming, cfg):
    user = Actor(message.phone, message.phone, "whatsapp")
    profile = profiles.find_profile(db, user)
    state = one(
        db,
        """SELECT draft,lang,assisted,pending,expected,lookup FROM whatsapp_conversations
                  WHERE phone=:p AND updated_at>=now()-interval '7 days'""",
        p=message.phone,
    )
    state = state or {
        "draft": {},
        "lang": profile.lang if profile else "en",
        "assisted": None,
        "pending": None,
        "expected": None,
        "lookup": {},
    }
    draft = state["draft"]
    cmd, source = message.button, message.text[:1000]
    if cmd in {"lang:en", "lang:hi"} or normalize(source) in {"hindi", "हिन्दी", "हिंदी", "english"}:
        lang = cmd.split(":")[1] if cmd else "en" if normalize(source) == "english" else "hi"
        state["lang"] = lang
        if draft:
            draft["lang"] = lang
        save(db, user.phone, state)
        return (
            consent_message(lang)
            if state["assisted"] is None
            else text(say(lang, "Language updated. Send your next message.", "भाषा बदली गई। अगला संदेश भेजें।"))
        )
    lang = state["lang"]
    if cmd in {"mode:ai", "mode:text"}:
        state["assisted"] = cmd == "mode:ai"
        save(db, user.phone, state)
        if profile:
            return show_menu(lang, profile.role == "worker")
    elif normalize(source) in {"privacy", "ai settings", "गोपनीयता"}:
        return consent_message(lang)

    if not profile and one(db, "SELECT 1 FROM profiles WHERE phone=:p", p=user.phone):
        if cmd == "connect:" + (state["pending"] or "!"):
            profile = profiles.reuse_confirmed_profile(db, user)
            state.update(draft={}, pending=None, expected=None)
            save(db, user.phone, state)
            return text(
                say(lang, "Existing profile connected: ", "मौजूदा प्रोफ़ाइल जुड़ गई: ") + profile.public_id
            )
        if (state["pending"] is None or state["expected"] != "connect") or cmd.startswith("connect:"):
            state["pending"], state["expected"] = token_urlsafe(16), "connect"
            save(db, user.phone, state)
        return buttons(
            say(
                lang,
                "This verified number already has a KaamPaas profile. Connect it to WhatsApp?",
                "इस सत्यापित नंबर की KaamPaas प्रोफ़ाइल मौजूद है। इसे WhatsApp से जोड़ें?",
            ),
            [("connect:" + state["pending"], say(lang, "Connect profile", "प्रोफ़ाइल जोड़ें"))],
        )

    if state["assisted"] is None and (not profile or message.kind == "audio"):
        return consent_message(lang)
    cat = dictionaries(db)
    assisted = bool(state["assisted"])
    if assisted and (source or message.kind == "audio"):
        try:
            rate_limit("whatsapp_assisted", user.phone, 10)
        except HTTPException as exc:
            if exc.status_code != 429:
                raise
            assisted = False
            if message.kind == "audio":
                return text(
                    say(
                        lang,
                        "Voice is busy. Wait a minute or send text.",
                        "आवाज़ अभी व्यस्त है। एक मिनट रुकें या लिखें।",
                    )
                )
    if message.kind == "audio":
        if not state["assisted"]:
            return text(
                say(
                    lang,
                    "Voice processing is off. Reply by text or type “privacy” to change it.",
                    "आवाज़ की सुविधा बंद है। लिखें या बदलने के लिए “गोपनीयता” भेजें।",
                )
            )
        try:
            source = provider.whatsapp_transcript(meta.audio(cfg, message.media), lang)
        except (meta.UnsupportedAudio, meta.ProviderUnavailable, HTTPException):
            source = ""
        if not source:
            return text(
                say(
                    lang,
                    "Could not hear the note. Type your reply or send a WhatsApp voice note under 45 seconds.",
                    "आवाज़ नहीं समझ आई। लिखें या 45 सेकंड से छोटा वॉइस नोट भेजें।",
                )
            )

    if profile:
        if cmd in {"availability:today", "availability:paused"} and profile.role == "worker":
            profiles.availability(db, profile, Availability(mode=cmd.split(":")[1]))
            return text(say(lang, "Availability updated.", "उपलब्धता बदल गई।"))
        if reply := application(db, profile, user, state, lang, cmd, source):
            return reply
        if reply := whatsapp_post.posting(
            db,
            profile,
            Incoming(message.id, message.phone, message.kind, source, cmd),
            state,
            cat,
            text=text,
            buttons=buttons,
            save=save,
            say=say,
            normalize=normalize,
            area_id=area_id,
            skills_from=skills_from,
            kinds_from=kinds_from,
            assisted=assisted,
        ):
            return reply
        direct = query_from(source)
        query = direct or nearby_fallback(source, cat, profile.role)
        if (not direct or message.kind == "audio") and source and assisted:
            result = assistant.classify(source, cat, profile.role)
            if (
                result
                and result.intent in assistant.BOARD_INTENTS[profile.role]
                and (result.intent != "help" or not query)
            ):
                query = result
        return (
            list_for(db, profile, query, lang, cat, state, user.phone)
            if query
            else show_menu(lang, profile.role == "worker")
        )

    if cmd.startswith("yes:"):
        if state["expected"] != "confirm" or cmd != "yes:" + (state["pending"] or "!"):
            return text(
                say(
                    lang,
                    "That confirmation expired. Send a message to review your current details.",
                    "पुष्टि समाप्त हो गई। नए विवरण देखने के लिए संदेश भेजें।",
                )
            )
        registration = dict(draft, lang=lang)
        if registration["role"] == "employer":
            registration.update(skills=[], kinds=[])
        profile = profiles.register(db, user, Onboarding(**registration))
        state.update(draft={}, pending=None, expected=None)
        save(db, user.phone, state)
        return text(
            say(lang, "Registered! Your KaamPaas ID: ", "पंजीकरण पूरा! आपकी KaamPaas ID: ")
            + profile.public_id
            + say(
                lang,
                "\nSend “nearby jobs” or “help” to continue.",
                "\nआगे बढ़ने के लिए “पास का काम” या “मदद” भेजें।",
            )
        )
    if cmd.startswith("edit:"):
        if cmd != "edit:" + (state["pending"] or "!"):
            return text(say(lang, "This review is no longer active.", "यह पुष्टि अब सक्रिय नहीं है।"))
        state.update(pending=None, expected="edit")
        save(db, user.phone, state)
        return text(
            say(
                lang,
                "Send the correction as “Name: …”, “Area: …”, “Role: …”, “Trade: …” or “Type: …”.",
                "सुधार इस तरह भेजें: “नाम: …”, “इलाका: …”, “भूमिका: …”, “हुनर: …” या “प्रकार: …”।",
            )
        )
    if cmd in {"role:worker", "role:employer"}:
        draft["role"] = cmd.split(":")[1]
    elif cmd in {"kind:short_term", "kind:permanent", "kind:both"}:
        draft["kinds"] = kinds_from(cmd.split(":")[1])
    elif source:
        expected = state["expected"]
        direct = handwritten(source, expected, cat)
        extracted = None
        if assisted and (not direct or "\n" in source or message.kind == "audio"):
            extracted = assistant.extract(source, cat, expected)
        if extracted:
            merge(draft, extracted.model_dump(exclude_none=True), cat)
        merge(draft, direct, cat)
        lang = draft.get("lang", lang)
        state["lang"] = lang
        if expected == "edit" and not direct and not (extracted and extracted.model_dump(exclude_none=True)):
            return text(
                say(
                    lang,
                    "Send the field and new value, for example “Area: Loni”.",
                    "नया विवरण लिखें, जैसे “इलाका: लोनी”।",
                )
            )
    if message.kind not in {"text", "audio", "interactive"}:
        return text(
            say(lang, "Send text or an optional WhatsApp voice note.", "लिखें या WhatsApp वॉइस नोट भेजें।")
        )
    if draft.get("role") == "employer":
        draft.pop("skills", None)
        draft.pop("kinds", None)
    state["expected"], reply = prompt(draft, lang, cat)
    state["pending"] = None
    if not reply:
        state["pending"], state["expected"] = token_urlsafe(16), "confirm"
        reply = buttons(
            onboarding_summary(draft, lang, cat),
            [
                ("yes:" + state["pending"], say(lang, "Yes", "हाँ")),
                ("edit:" + state["pending"], say(lang, "Edit details", "विवरण बदलें")),
            ],
        )
    save(db, user.phone, state)
    return reply
