import base64
import io
import wave

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from firebase_admin import auth

from app.integrations.speech import provider
from app.integrations.speech.provider import pcm
from app.models import today
from app.settings import settings
from main import app


def test_request_guards_and_revocation(database, monkeypatch):
    monkeypatch.setenv("WEB_ORIGINS", "https://localhost")
    settings.cache_clear()
    try:
        with TestClient(app, base_url="https://localhost") as client:
            assert client.get("/api/me").status_code == 401
            csrf = client.get("/api/auth/csrf").json()["token"]
            assert client.post("/api/auth/logout", headers={"Origin": "https://localhost"}).status_code == 403
            assert (
                client.post(
                    "/api/auth/logout", headers={"Origin": "https://different.test", "X-CSRF-Token": csrf}
                ).status_code
                == 403
            )
            response = client.post(
                "/api/auth/logout", headers={"Origin": "https://localhost", "X-CSRF-Token": csrf}
            )
            assert response.status_code == 200
            checked = []

            def revoked(cookie, *, check_revoked, app):
                checked.append(check_revoked)
                raise ValueError("expired or revoked")

            monkeypatch.setattr(auth, "verify_session_cookie", revoked)
            client.cookies.set("__Host-session", "revoked-test-fixture")
            response = client.get("/api/me")
            assert response.status_code == 401 and checked == [True]
            assert "no-store" in response.headers["Cache-Control"]
    finally:
        settings.cache_clear()


def test_emulator_is_rejected_in_deployments(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:19099")
    settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="emulation"):
            settings()
    finally:
        settings.cache_clear()


def test_duration_is_measured_from_pcm_not_client_claims():
    def sample(frames):
        data = io.BytesIO()
        with wave.open(data, "wb") as f:
            f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            f.writeframes(bytes(frames * 2))
        return base64.b64encode(data.getvalue()).decode()

    assert len(base64.b64decode(pcm(sample(3200)))) == 6400
    with pytest.raises(HTTPException):
        pcm(sample(240001))


def test_readback_uses_catalog_and_never_reads_private_notes(db, monkeypatch):
    heard = {}

    def synthesize(endpoint, payload):
        heard.update(payload)
        assert endpoint.endswith("text:synthesize")
        return {"audioContent": "audio-fixture"}

    monkeypatch.setattr(provider, "call", synthesize)
    listing = {
        "skill": "mason",
        "area": "201206-duhai",
        "kind": "short_term",
        "starts": today(),
        "deadline": today(),
        "pay": 75000,
        "unit": "day",
        "description": "Private draft notes",
    }
    result = provider.speak(provider.summary(db, listing, "hi"), "hi")
    assert result == {"audio": "audio-fixture"}
    assert heard["voice"]["languageCode"] == "hi-IN"
    assert "750 रुपये प्रति दिन" in heard["input"]["text"]
    assert "2 0 1 2 0 6" in heard["input"]["text"]
    assert "Private draft notes" not in heard["input"]["text"]
