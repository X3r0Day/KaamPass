from datetime import date, time
from decimal import Decimal, InvalidOperation
from secrets import token_urlsafe
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.integrations.whatsapp import assistant
from app.models import JobDraft, Publish, today
from app.services import matching


def posting(
    db,
    profile,
    message,
    state,
    catalog,
    *,
    text,
    buttons,
    save,
    say,
    normalize,
    area_id,
    skills_from,
    kinds_from,
    assisted,
):
    lang = state["lang"]
    source, command = message.text.strip(), message.button
    if profile.role != "employer":
        return None
    start = normalize(source) in {"post a job", "post job", "काम पोस्ट करें", "नौकरी पोस्ट करें"}
    action = state["expected"] in {"post", "post_review"}
    if not (start or action or command.startswith("post:")):
        return None
    if start and not action:
        state.update(expected="post", pending=None, lookup={"posting": {}})
        save(db, message.phone, state)
        return text(
            say(
                lang,
                "Describe the job in text or by voice (if enabled). For guided text, send lines such as:\n"
                "Trade: Mason\nArea: Duhai\nType: short-term\nStart: YYYY-MM-DD\nEnd: YYYY-MM-DD\n"
                "Time: 09:00\nDeadline: YYYY-MM-DD\nPay: 750\nUnit: day\nDescription: optional\n"
                "Nothing will be posted until you confirm. Type “cancel draft” to leave.",
                "काम लिखें या (चालू होने पर) बोलें। लिखने के लिए हर विवरण अलग लाइन में दें:\n"
                "हुनर: राजमिस्त्री\nइलाका: दुहाई\nप्रकार: अस्थायी\nशुरू: YYYY-MM-DD\nअंत: YYYY-MM-DD\n"
                "समय: 09:00\nअंतिम तारीख: YYYY-MM-DD\nराशि: 750\nअवधि: दिन\nविवरण: वैकल्पिक\n"
                "पुष्टि तक कुछ प्रकाशित नहीं होगा। छोड़ने के लिए “मसौदा रद्द” लिखें।",
            )
        )
    draft = state["lookup"].get("posting")
    if draft is None:
        return text(
            say(
                lang,
                "That review expired. Type “post a job” to start again.",
                "पुष्टि समाप्त हुई। फिर “काम पोस्ट करें” लिखें।",
            )
        )
    if normalize(source) in {"cancel draft", "मसौदा रद्द"}:
        state.update(expected=None, pending=None, lookup={})
        save(db, message.phone, state)
        return text(say(lang, "Draft cleared.", "मसौदा हट गया।"))
    if command.startswith("post:"):
        if state["expected"] != "post_review" or command != "post:" + (state["pending"] or "!"):
            return text(
                say(
                    lang,
                    "That confirmation expired. Send a correction to review again.",
                    "पुष्टि समाप्त हुई। फिर जाँचने के लिए सुधार भेजें।",
                )
            )
        try:
            listing = Publish(**draft, share_contact=True, submission_key=UUID(state["lookup"]["submission"]))
            matching.publish(db, profile, listing)
        except (HTTPException, ValidationError):
            state.update(expected="post", pending=None)
            save(db, message.phone, state)
            return text(
                say(
                    lang,
                    "The opening could not be posted. Check the dates and the work area and review again.",
                    "काम पोस्ट नहीं हुआ। तारीख और इलाका जाँचकर फिर कोशिश करें।",
                )
            )
        state.update(expected=None, pending=None, lookup={})
        save(db, message.phone, state)
        return text(
            say(
                lang,
                "Opening posted. Send “my postings” to check its status.",
                "काम पोस्ट हो गया। स्थिति जानने के लिए “मेरे पोस्ट” भेजें।",
            )
        )

    labels = {
        "trade": "skill",
        "हुनर": "skill",
        "area": "area",
        "इलाका": "area",
        "type": "kind",
        "प्रकार": "kind",
        "start": "starts",
        "शुरू": "starts",
        "end": "ends",
        "अंत": "ends",
        "time": "shift_time",
        "समय": "shift_time",
        "deadline": "deadline",
        "अंतिम तारीख": "deadline",
        "pay": "rupees",
        "राशि": "rupees",
        "unit": "unit",
        "अवधि": "unit",
        "description": "description",
        "विवरण": "description",
    }
    direct = {}
    for line in source.splitlines():
        label, sep, value = line.partition(":")
        if sep and (field := labels.get(normalize(label))):
            direct[field] = value.strip()
    missing = state["lookup"].get("missing")
    if not direct and not assisted and source and missing:
        direct[missing] = source
    parsed = (
        assistant.extract_posting(source, catalog, today(), missing)
        if (source and assisted and (not direct or message.kind == "audio"))
        else None
    )
    fields = {**(parsed.model_dump(exclude_none=True) if parsed else {}), **direct}
    allowed_units = {
        "day": "day",
        "दिन": "day",
        "shift": "shift",
        "पाली": "shift",
        "month": "month",
        "महीना": "month",
        "job": "job",
        "काम": "job",
    }
    skills = {r["id"]: r for r in catalog["skills"]}
    places = {r["id"]: r for r in catalog["areas"]}
    for field, value in fields.items():
        if field == "skill":
            values = skills_from(str(value), catalog)
            if len(values) == 1:
                draft[field] = values[0]
        elif field == "area" and (choice := area_id(str(value), catalog)):
            draft[field] = choice
        elif field == "kind" and len(kinds := kinds_from(str(value))) == 1:
            draft[field] = kinds[0]
        elif field in {"starts", "ends", "deadline", "shift_time"}:
            try:
                draft[field] = (time if field == "shift_time" else date).fromisoformat(str(value)).isoformat()
            except ValueError:
                pass
        elif field == "rupees":
            try:
                paise = Decimal(str(value).replace("₹", "").replace(",", "").strip()) * 100
                if paise.is_finite() and 0 < paise <= 1_000_000_000 and paise == paise.to_integral_value():
                    draft["pay"] = int(paise)
            except InvalidOperation:
                pass
        elif field == "unit" and normalize(str(value)) in allowed_units:
            draft[field] = allowed_units[normalize(str(value))]
        elif field == "description":
            draft[field] = str(value)[:800]
    needed = [
        ("skill", "Trade", "हुनर"),
        ("area", "Area", "इलाका"),
        ("kind", "Type", "प्रकार"),
        ("starts", "Start", "शुरू"),
        ("deadline", "Deadline", "अंतिम तारीख"),
        ("rupees", "Pay", "राशि"),
        ("unit", "Unit", "अवधि"),
    ]
    if draft.get("kind") == "permanent":
        draft.pop("ends", None)
        draft.pop("shift_time", None)
    else:
        needed.append(("ends", "End", "अंत"))
        if draft.get("starts") == draft.get("ends"):
            needed.append(("shift_time", "Time", "समय"))
    missing_field = next(
        ((f, en, hi) for f, en, hi in needed if not draft.get("pay" if f == "rupees" else f)), None
    )
    state["pending"] = None
    if missing_field:
        f, en, hi = missing_field
        state["lookup"]["missing"], state["expected"] = f, "post"
        save(db, message.phone, state)
        choices = (
            ", ".join(row[lang] for row in skills.values())
            if f == "skill"
            else ", ".join(f"{row[lang]} ({row['pin']})" for row in places.values())
            if f == "area"
            else "YYYY-MM-DD"
            if f in {"starts", "ends", "deadline"}
            else "HH:MM"
            if f == "shift_time"
            else say(lang, "short-term / permanent", "अस्थायी / स्थायी")
            if f == "kind"
            else say(lang, "day / shift / month / job", "दिन / पाली / महीना / काम")
            if f == "unit"
            else "750"
        )
        return text(
            say(lang, f"Still needed: {en}. Reply with a value:\n", f"यह विवरण चाहिए: {hi}। सही मान भेजें:\n")
            + choices
        )
    try:
        valid = JobDraft(**draft)
        if valid.deadline < today():
            raise ValueError
    except (ValidationError, ValueError):
        state.update(expected="post", pending=None)
        save(db, message.phone, state)
        return text(
            say(
                lang,
                "Check the dates. The deadline can't be in the past or after the start. "
                "Short-term work needs an end date; a one-day shift needs a time.",
                "तारीखें जाँचें। अंतिम आवेदन तारीख बीती हुई या शुरू होने के बाद नहीं हो सकती। अस्थायी काम की अंत तारीख दें; एक दिन की पाली का समय दें।",
            )
        )
    state.update(expected="post_review", pending=token_urlsafe(16))
    state["lookup"]["submission"] = str(uuid4())
    save(db, message.phone, state)
    place = places[valid.area]
    body = (
        f"{skills[valid.skill][lang]} · {place[lang]} ({place['pin']})\n"
        f"{say(lang, 'Permanent', 'स्थायी') if valid.kind == 'permanent' else say(lang, 'Short-term', 'अस्थायी')}\n"
        f"{valid.starts}{' – ' + str(valid.ends) if valid.ends else ''} {valid.shift_time or ''}\n"
        f"₹{Decimal(valid.pay) / 100} / {valid.unit}\n"
        f"{say(lang, 'Apply by', 'आवेदन की अंतिम तारीख')}: {valid.deadline}\n"
        f"{valid.description[:350]}\n"
        + say(
            lang,
            "Tap Publish to post and share your number only with the worker you assign.",
            "प्रकाशित करें दबाने पर काम पोस्ट होगा। नंबर केवल चुने गए कामगार से साझा होगा।",
        )
    )
    return buttons(body, [("post:" + state["pending"], say(lang, "Publish", "प्रकाशित करें"))])
