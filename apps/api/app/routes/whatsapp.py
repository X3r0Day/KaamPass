import hmac
import json
import re
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from psycopg.types.json import Jsonb
from starlette.concurrency import run_in_threadpool

from app.db.store import engine, one, run
from app.integrations.whatsapp import meta
from app.services import whatsapp

router = APIRouter(prefix="/api/whatsapp")


@router.get("/webhook", response_class=PlainTextResponse)
def challenge(request: Request):
    cfg = meta.config()
    if not cfg:
        raise HTTPException(404, "not_found")
    query = request.query_params
    token = query.get("hub.verify_token", "")
    value = query.get("hub.challenge", "")
    if query.get("hub.mode") != "subscribe" or not hmac.compare_digest(
        token.encode(), cfg.verify_token.encode()
    ):
        raise HTTPException(403, "verification_failed")
    if not re.fullmatch(r"[0-9]{1,30}", value):
        raise HTTPException(422, "invalid_challenge")
    return value


def messages(payload: dict, cfg):
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if (
                change.get("field") != "messages"
                or value.get("metadata", {}).get("phone_number_id") != cfg.number
            ):
                continue
            for message in value.get("messages", []):
                source, mid = message.get("from", ""), message.get("id", "")
                timestamp = message.get("timestamp", "")
                if not re.fullmatch(r"[1-9][0-9]{7,14}", source) or not re.fullmatch(
                    r"wamid\.[A-Za-z0-9_.=+/-]{1,250}", mid
                ):
                    continue
                if (
                    not timestamp.isdecimal()
                    or len(timestamp) > 12
                    or not -300 < time.time() - int(timestamp) < 7 * 86400
                ):
                    continue
                kind = message.get("type", "")
                reply = message.get("interactive", {})
                button = (
                    reply.get("button_reply", {}).get("id", "") if reply.get("type") == "button_reply" else ""
                )
                yield whatsapp.Incoming(
                    mid,
                    "+" + source,
                    kind,
                    message.get("text", {}).get("body", ""),
                    button[:120],
                    message.get("audio", {}).get("id", ""),
                )


def deliver(cfg, incoming):
    with engine().begin() as db:
        # Serialize draft updates and reserve each Meta message before any provider calls.
        run(db, "SELECT pg_advisory_xact_lock(hashtextextended(:phone,0))", phone=incoming.phone)
        created = one(
            db,
            "INSERT INTO whatsapp_events(id) VALUES (:id) ON CONFLICT DO NOTHING RETURNING id",
            id=incoming.id,
        )
        if created:
            reply = whatsapp.handle(db, incoming, cfg)
            run(
                db, "UPDATE whatsapp_events SET reply=:reply WHERE id=:id", id=incoming.id, reply=Jsonb(reply)
            )
            if secrets.randbelow(64) == 0:
                run(db, "DELETE FROM whatsapp_events WHERE created_at<now()-interval '8 days'")
                run(db, "DELETE FROM whatsapp_conversations WHERE updated_at<now()-interval '8 days'")
        event = one(
            db,
            """UPDATE whatsapp_events SET claimed_until=now()+interval '60 seconds'
            WHERE id=:id AND reply IS NOT NULL AND sent_at IS NULL AND (claimed_until IS NULL OR claimed_until < now())
            RETURNING reply""",
            id=incoming.id,
        )
        pending = not event and bool(
            one(db, "SELECT 1 FROM whatsapp_events WHERE id=:id AND sent_at IS NULL", id=incoming.id)
        )
    if pending:
        raise meta.ProviderUnavailable()
    if not event:
        return
    try:
        meta.send(cfg, incoming.phone, event["reply"])
    except meta.ProviderUnavailable:
        with engine().begin() as db:
            run(
                db,
                "UPDATE whatsapp_events SET claimed_until=NULL WHERE id=:id AND sent_at IS NULL",
                id=incoming.id,
            )
        raise
    with engine().begin() as db:
        run(
            db,
            "UPDATE whatsapp_events SET reply=NULL,sent_at=now(),claimed_until=NULL WHERE id=:id",
            id=incoming.id,
        )


@router.post("/webhook")
async def webhook(request: Request):
    cfg = meta.config()
    if not cfg:
        raise HTTPException(404, "not_found")
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > 262_144:
            raise HTTPException(413, "body_too_large")
    if not meta.signed(cfg.secret, bytes(raw), request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "signature_required")
    try:
        payload = json.loads(raw)
        batch = list(messages(payload, cfg))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, "invalid_webhook") from None
    try:
        for item in batch:
            await run_in_threadpool(deliver, cfg, item)
    except meta.ProviderUnavailable:
        raise HTTPException(503, "retry_delivery") from None
    return {"ok": True}
