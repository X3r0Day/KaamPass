import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import requests

GRAPH = "https://graph.facebook.com"
AUDIO_MAX = 1_500_000


class ProviderUnavailable(Exception):
    pass


class UnsupportedAudio(Exception):
    pass


@dataclass(frozen=True)
class Config:
    number: str
    secret: str
    token: str
    verify_token: str
    version: str


@lru_cache
def config() -> Config | None:
    if os.getenv("WHATSAPP_ENABLED", "").lower() != "true":
        return None
    values = [
        os.getenv(f"WHATSAPP_{k}", "")
        for k in ("PHONE_NUMBER_ID", "APP_SECRET", "ACCESS_TOKEN", "VERIFY_TOKEN")
    ]
    version = os.getenv("WHATSAPP_GRAPH_VERSION", "v26.0")
    if not any(values):
        return None
    if (
        not all(values)
        or not re.fullmatch(r"[0-9]{5,30}", values[0])
        or not re.fullmatch(r"v[0-9]{2}\.0", version)
    ):
        raise RuntimeError("Complete Meta Cloud API configuration is required")
    return Config(*values, version)


def signed(secret: str, body: bytes, header: str) -> bool:
    return bool(re.fullmatch(r"sha256=[a-f0-9]{64}", header)) and hmac.compare_digest(
        header, "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    )


def graph(cfg: Config, method: str, path: str, **options):
    try:
        response = requests.request(
            method,
            f"{GRAPH}/{cfg.version}/{path}",
            headers={"Authorization": f"Bearer {cfg.token}"},
            timeout=(3, 8),
            allow_redirects=False,
            **options,
        )
        if not response.ok or response.is_redirect:
            raise ProviderUnavailable()
        return response.json()
    except (requests.RequestException, ValueError):
        raise ProviderUnavailable() from None


def send(cfg: Config, phone: str, message: dict):
    graph(
        cfg,
        "POST",
        f"{cfg.number}/messages",
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone.lstrip("+"),
            **message,
        },
    )


def audio(cfg: Config, media_id: str) -> bytes:
    if not re.fullmatch(r"[0-9]{5,40}", media_id):
        raise UnsupportedAudio()
    data = graph(cfg, "GET", media_id, params={"phone_number_id": cfg.number})
    if str(data.get("mime_type", "")).split(";")[0].strip().lower() not in {"audio/ogg", "application/ogg"}:
        raise UnsupportedAudio()
    if not isinstance(data.get("file_size"), int) or not 0 < data["file_size"] <= AUDIO_MAX:
        raise UnsupportedAudio()
    uri = urlsplit(data.get("url", ""))
    if uri.scheme != "https" or uri.netloc not in {
        "lookaside.fbsbx.com",
        "lookaside.facebook.com",
        "graph.facebook.com",
    }:
        raise UnsupportedAudio()
    try:
        with requests.get(
            uri.geturl(),
            headers={"Authorization": f"Bearer {cfg.token}"},
            timeout=(3, 8),
            stream=True,
            allow_redirects=False,
        ) as response:
            if not response.ok or response.is_redirect:
                raise ProviderUnavailable()
            raw = bytearray()
            for chunk in response.iter_content(16384):
                raw.extend(chunk)
                if len(raw) > AUDIO_MAX:
                    raise UnsupportedAudio()
        return bytes(raw)
    except requests.RequestException:
        raise ProviderUnavailable() from None
