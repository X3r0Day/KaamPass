import base64
import binascii
import io
import json
import os
import wave
from datetime import date

import google.auth
from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from requests import RequestException

from app.db.store import one


def pcm(encoded: str):
    try:
        data = base64.b64decode(encoded, validate=True)
        if len(data) > 1_000_000:
            raise ValueError
        with wave.open(io.BytesIO(data)) as wav:
            frames = wav.getnframes()
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
                1,
                2,
                16000,
                "NONE",
            ):
                raise ValueError
            if not 1600 <= frames <= 240000:
                raise ValueError
            samples = wav.readframes(frames)
            if len(samples) != frames * 2:
                raise ValueError
        return base64.b64encode(samples).decode()
    except (wave.Error, EOFError, binascii.Error, ValueError):
        raise HTTPException(422, "audio_format") from None


def call(endpoint, payload):
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    try:
        raw = os.getenv("SPEECH_CREDENTIALS_JSON")
        credentials = (
            service_account.Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
            if raw
            else google.auth.default(scopes=scopes)[0]
        )
        with AuthorizedSession(credentials) as session:
            result = session.post(endpoint, json=payload, timeout=(4, 18))
            result.raise_for_status()
            return result.json()
    except (GoogleAuthError, RequestException, ValueError, KeyError):
        raise HTTPException(503, "speech_unavailable") from None


def transcribe(encoded, lang):
    payload = {
        "audio": {"content": pcm(encoded)},
        "config": {
            "encoding": "LINEAR16",
            "sampleRateHertz": 16000,
            "languageCode": f"{lang}-IN",
            "model": os.getenv("SPEECH_MODEL", "default"),
        },
    }
    result = call("https://speech.googleapis.com/v1/speech:recognize", payload)
    lines = [r["alternatives"][0]["transcript"] for r in result.get("results", []) if r.get("alternatives")]
    if not lines:
        raise HTTPException(422, "not_heard")
    return {"transcript": " ".join(lines)[:1200]}


def whatsapp_transcript(raw: bytes, lang: str):
    # Ogg Opus timestamps always count at 48 kHz. Bound decoded duration before calling Google.
    offset = 0
    serial = None
    granule = 0
    while offset + 27 <= len(raw):
        if raw[offset : offset + 5] != b"OggS\x00":
            break
        segments = raw[offset + 26]
        start = offset + 27 + segments
        end = start + sum(raw[offset + 27 : start])
        if start > len(raw) or end > len(raw):
            break
        stream = raw[offset + 14 : offset + 18]
        if serial is None:
            serial = stream
            if end - start < 19 or raw[start : start + 8] != b"OpusHead" or raw[start + 9] != 1:
                break
        if stream != serial:
            break
        timestamp = int.from_bytes(raw[offset + 6 : offset + 14], "little", signed=True)
        if timestamp >= 0:
            if timestamp < granule or timestamp > 45 * 48000:
                break
            granule = timestamp
        offset = end
    if offset != len(raw) or granule < 4800:
        raise HTTPException(422, "audio_format")
    result = call(
        "https://speech.googleapis.com/v1/speech:recognize",
        {
            "audio": {"content": base64.b64encode(raw).decode()},
            "config": {
                "encoding": "OGG_OPUS",
                "sampleRateHertz": 48000,
                "languageCode": f"{lang}-IN",
                "model": os.getenv("SPEECH_MODEL", "default"),
            },
        },
    )
    transcript = " ".join(
        r["alternatives"][0]["transcript"] for r in result.get("results", []) if r.get("alternatives")
    )
    return transcript[:1000]


def summary(db, job, lang):
    skill = one(db, "SELECT en,hi FROM skills WHERE id=:id", id=job["skill"])
    place = one(db, "SELECT en,hi,pin FROM localities WHERE id=:id", id=job["area"])
    if not place or not skill:
        raise HTTPException(422, "invalid_fields")
    amount = f"{job['pay'] / 100:.2f}".rstrip("0").rstrip(".")
    units = {"day": "दिन", "month": "महीना", "shift": "पाली", "job": "काम"}

    def day(value: date):
        return value.strftime("%d/%m/%Y")

    start = day(job["starts"])
    end = day(job["ends"]) if job.get("ends") else None
    time = str(job.get("shift_time") or "")[:5]
    deadline = day(job["deadline"])
    pin = " ".join(place["pin"])
    if lang == "hi":
        kind = "स्थायी नौकरी" if job["kind"] == "permanent" else "अस्थायी काम"
        return (
            f"{skill[lang]}, {place[lang]}। पिन कोड {pin}। {kind}। {amount} रुपये प्रति {units[job['unit']]}। "
            f"शुरुआत {start} {time}।" + (f" अंत {end}।" if end else "") + f" आवेदन की अंतिम तारीख {deadline}।"
        )
    kind = "Permanent opening" if job["kind"] == "permanent" else "Short-term work"
    return (
        f"{skill[lang]} in {place[lang]}. Postal PIN {pin}. {kind}. {amount} rupees per {job['unit']}. "
        f"Starts {start} {time}." + (f" Ends {end}." if end else "") + f" Apply by {deadline}."
    )


def speak(text, lang):
    voice = {"languageCode": f"{lang}-IN"}
    if name := os.getenv(f"TTS_VOICE_{lang.upper()}"):
        voice["name"] = name
    result = call(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        {"input": {"text": text}, "voice": voice, "audioConfig": {"audioEncoding": "MP3"}},
    )
    return {"audio": result["audioContent"]}
