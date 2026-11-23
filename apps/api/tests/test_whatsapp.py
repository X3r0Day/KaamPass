import json
import struct
import time
from hashlib import sha256
from hmac import new
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.store import one
from app.integrations.speech import provider
from app.integrations.whatsapp import assistant, meta
from app.models import Onboarding, today
from app.routes.whatsapp import deliver
from app.security import Actor
from app.services.profiles import find_profile, register, reuse_confirmed_profile
from app.services.whatsapp import Incoming, handle
from app.settings import settings
from main import app

CFG = meta.Config("12345678", "test-app-secret", "test-access-token", "verify-fixture", "v26.0")


def reply_id(message, prefix):
    return next(
        x["reply"]["id"]
        for x in message["interactive"]["action"]["buttons"]
        if x["reply"]["id"].startswith(prefix)
    )


def body(message):
    return message.get("text", {}).get("body") or message["interactive"]["body"]["text"]


def chat(db, phone, text="", button="", *, kind=None, media=""):
    return handle(
        db,
        Incoming(
            "wamid." + uuid4().hex, phone, kind or ("interactive" if button else "text"), text, button, media
        ),
        CFG,
    )


def test_whatsapp_registration_asks_only_for_missing_fields_and_requires_current_button(db):
    p = "+919876500067"
    consent = chat(db, p, "Hi")
    assert "Free-model data" in body(consent)
    mode = reply_id(consent, "mode:text")
    chat(db, p, button=mode)
    followup = chat(db, p, "Role: Worker\nName: Anita\nTrade: Mason\nType: Both")
    assert "Which Ghaziabad work area?" in body(followup)
    assert "Which Ghaziabad work area?" in body(chat(db, p, "201206"))  # PIN alone is ambiguous.
    review = chat(db, p, "Duhai")
    pending = reply_id(review, "yes:")
    assert "Duhai (201206)" in body(review) and "Anita" in body(review)
    refreshed = chat(db, p, "Name: Anita Singh")
    assert "Anita Singh" in body(refreshed)
    assert "expired" in body(chat(db, p, button=pending))
    assert not one(db, "SELECT 1 FROM profiles WHERE phone=:p", p=p)
    current = reply_id(chat(db, p, "yes"), "yes:")
    assert not one(db, "SELECT 1 FROM profiles WHERE phone=:p", p=p)
    assert "Registered!" in body(chat(db, p, button=current))
    profile = one(db, "SELECT public_id,name,discoverable FROM profiles WHERE phone=:p", p=p)
    assert (
        profile["public_id"].startswith("WKR-")
        and profile["name"] == "Anita Singh"
        and not profile["discoverable"]
    )
    assert one(db, "SELECT provider FROM identity_bindings WHERE phone=:p", p=p)["provider"] == "whatsapp"


def test_voice_uses_google_then_deepseek_and_reads_scoped_real_matches(db, monkeypatch):
    w, e = "+919876545560", "+919876545561"
    chat(db, w, button="mode:ai")
    calls = []

    def media(cfg, media_id):
        calls.append(("media", media_id))
        return b"opus fixture"

    def transcript(data, lang):
        calls.append(("speech", lang))
        return "A worker from Duhai" if len(calls) < 4 else "Show nearby masonry shifts"

    def extract(text, catalog, expected):
        calls.append(("parse", expected))
        return assistant.Fields(
            role="worker", name="Lata", area="201206-duhai", skills=["mason"], kinds=["short_term"]
        )

    def classify(text, catalog, role):
        calls.append(("classify", text))
        return assistant.Query(intent="matches", skill="mason", kind="short_term")

    monkeypatch.setattr(meta, "audio", media)
    monkeypatch.setattr(provider, "whatsapp_transcript", transcript)
    monkeypatch.setattr(assistant, "extract", extract)
    monkeypatch.setattr(assistant, "classify", classify)
    worker = chat(db, w, kind="audio", media="789012")
    chat(db, w, button=reply_id(worker, "yes:"))
    assert calls == [("media", "789012"), ("speech", "en"), ("parse", "role")]

    chat(db, e, button="mode:text")
    employer = chat(db, e, "Role: Employer\nName: Local shop\nArea: Duhai")
    chat(db, e, button=reply_id(employer, "yes:"))
    chat(db, e, "post a job")
    d = today().isoformat()
    offer = f"Trade: Mason\nArea: Duhai\nType: short-term\nStart: {d}\nEnd: {d}\nDeadline: {d}\nTime: 09:00\nPay: 825\nDescription: Repair site"
    assert "Still needed: Unit" in body(chat(db, e, offer))
    review = chat(db, e, "day")
    confirm = reply_id(review, "post:")
    assert not one(db, "SELECT 1 FROM jobs WHERE description='Repair site'")
    chat(db, e, button=confirm)
    other = offer.replace("Duhai", "Loni").replace("Repair site", "Outside area")
    chat(db, e, "post a job")
    publish = chat(db, e, other + "\nUnit: day")
    chat(db, e, button=reply_id(publish, "post:"))
    listing = body(chat(db, w, kind="audio", media="789013"))
    assert "₹825/day" in listing and "Repair site" in listing and "Outside area" not in listing
    assert [name for name, *_ in calls][-3:] == ["media", "speech", "classify"]
    apply = chat(db, w, "apply 1")
    interested = "SELECT 1 FROM interests JOIN profiles ON worker=public_id WHERE phone=:phone"
    assert not one(db, interested, phone=w)
    chat(db, w, button=reply_id(apply, "apply:"))
    assert one(db, interested, phone=w)


def test_guided_mode_never_sends_audio_or_text_to_providers(db, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("guided mode called a provider")

    monkeypatch.setattr(assistant, "extract", forbidden)
    monkeypatch.setattr(meta, "audio", forbidden)
    p = "+919876500073"
    chat(db, p, button="mode:text")
    assert "Voice processing is off" in body(chat(db, p, kind="audio", media="915842"))
    assert "display" in body(chat(db, p, button="role:worker"))


def test_signed_webhook_challenge_and_duplicate_delivery(database, monkeypatch):
    monkeypatch.setattr(meta, "config", lambda: CFG)
    sent = []
    monkeypatch.setattr(meta, "send", lambda cfg, phone, message: sent.append((phone, message)))
    phone = "919876500081"
    event = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": CFG.number},
                            "messages": [
                                {
                                    "from": phone,
                                    "id": "wamid." + uuid4().hex,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "Hi"},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }
    raw = json.dumps(event).encode()
    signed = "sha256=" + new(CFG.secret.encode(), raw, sha256).hexdigest()
    with TestClient(app, base_url="https://localhost") as client:
        path = "/api/whatsapp/webhook"
        response = client.get(
            path,
            params={"hub.mode": "subscribe", "hub.verify_token": CFG.verify_token, "hub.challenge": "123456"},
        )
        assert response.text == "123456"
        assert client.post(path, content=raw).status_code == 403
        assert (
            client.post(path, content=raw + b" ", headers={"x-hub-signature-256": signed}).status_code == 403
        )
        for _ in range(2):
            assert client.post(path, content=raw, headers={"x-hub-signature-256": signed}).status_code == 200
    assert len(sent) == 1 and sent[0][0] == "+" + phone


def test_send_retries_do_not_recompute_reply(database, monkeypatch):
    received = []

    def flaky(cfg, phone, reply):
        received.append(reply)
        if len(received) == 1:
            raise meta.ProviderUnavailable()

    monkeypatch.setattr(meta, "send", flaky)
    incoming = Incoming("wamid." + uuid4().hex, "+919876500087", "text", "Hi")
    try:
        deliver(CFG, incoming)
    except meta.ProviderUnavailable:
        pass
    deliver(CFG, incoming)
    deliver(CFG, incoming)
    assert len(received) == 2 and received[0] == received[1]


def test_whatsapp_only_requires_no_firebase_credentials(monkeypatch):
    monkeypatch.setenv("WEB_PHONE_AUTH_ENABLED", "false")
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    settings.cache_clear()
    try:
        assert not settings().phone_auth_enabled
        with TestClient(app, base_url="https://localhost") as client:
            assert client.get("/api/me").status_code == 401
    finally:
        settings.cache_clear()


def test_paused_whatsapp_does_not_accept_callbacks_even_with_credentials(monkeypatch):
    for name, value in {
        "ENABLED": "false",
        "PHONE_NUMBER_ID": CFG.number,
        "APP_SECRET": CFG.secret,
        "ACCESS_TOKEN": CFG.token,
        "VERIFY_TOKEN": CFG.verify_token,
    }.items():
        monkeypatch.setenv("WHATSAPP_" + name, value)
    meta.config.cache_clear()
    try:
        with TestClient(app, base_url="https://localhost") as client:
            assert client.get("/api/whatsapp/webhook").status_code == 404
            assert client.post("/api/whatsapp/webhook", json={}).status_code == 404
    finally:
        meta.config.cache_clear()


def test_verified_whatsapp_and_website_can_link_one_public_id(db):
    phone = "+919876500099"
    web = Actor("test-firebase-subject", phone)
    original = register(
        db, web, Onboarding(role="employer", name="Example Workshop", lang="en", area="201206-duhai")
    )
    messenger = Actor(phone, phone, "whatsapp")
    assert find_profile(db, messenger) is None
    with pytest.raises(HTTPException, match="identity_conflict"):
        register(db, messenger, Onboarding(role="employer", name="Changed", lang="en", area="201206-duhai"))
    prompt = chat(db, phone, "Hi")
    assert "connect" in body(prompt).lower() and original.public_id not in body(prompt)
    assert original.public_id in body(chat(db, phone, button=reply_id(prompt, "connect:")))
    assert reuse_confirmed_profile(db, messenger).name == "Example Workshop"


def test_voice_container_is_checked_before_google(monkeypatch):
    def page(granule, sequence, packet):
        return (
            b"OggS" + struct.pack("<BBqIII", 0, 0, granule, 9, sequence, 0) + bytes((1, len(packet))) + packet
        )

    raw = page(0, 0, b"OpusHead" + bytes((1, 1)) + bytes(9)) + page(48000, 1, b"audio")
    seen = []

    def google(endpoint, payload):
        seen.append(payload)
        assert endpoint == "https://speech.googleapis.com/v1/speech:recognize"
        return {"results": [{"alternatives": [{"transcript": "Nearby jobs"}]}]}

    monkeypatch.setattr(provider, "call", google)
    assert provider.whatsapp_transcript(raw, "hi") == "Nearby jobs"
    assert seen[0]["config"]["encoding"] == "OGG_OPUS" and seen[0]["config"]["languageCode"] == "hi-IN"
    with pytest.raises(HTTPException, match="audio_format"):
        provider.whatsapp_transcript(raw + page(46 * 48000, 2, b"audio"), "en")
    assert len(seen) == 1
