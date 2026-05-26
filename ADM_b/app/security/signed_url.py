"""Short-lived HMAC-signed tokens for audio streaming and download.

`kind` ("stream" / "download") is included in the HMAC payload but NOT in
the URL — preventing an attacker from re-purposing a stream URL as a
download URL.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from app.config import get_settings

settings = get_settings()

_DOWNLOAD_TTL_SECONDS = 600  # 10 min for resumable downloads


class SignedURLError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sign(kind: str, *parts: str) -> str:
    msg = f"{kind}:" + ":".join(parts)
    return hmac.new(
        settings.SIGNED_URL_SECRET.encode(), msg.encode(), hashlib.sha256
    ).hexdigest()


def issue_stream(audio_id: str, start: int) -> dict:
    exp = int(time.time()) + settings.SIGNED_URL_TTL_SECONDS
    sig = _sign("stream", audio_id, str(start), str(exp))
    return {"audio_id": audio_id, "start": start, "exp": exp, "sig": sig}


def verify_stream(audio_id: str, start: int, exp: int, sig: str) -> None:
    expected = _sign("stream", audio_id, str(start), str(exp))
    if not hmac.compare_digest(expected, sig):
        raise SignedURLError("INVALID_SIGNATURE", "invalid or tampered signature")
    if int(time.time()) > exp:
        raise SignedURLError("URL_EXPIRED", "stream URL has expired")


def issue_download(audio_id: str) -> dict:
    exp = int(time.time()) + _DOWNLOAD_TTL_SECONDS
    sig = _sign("download", audio_id, str(exp))
    return {"audio_id": audio_id, "exp": exp, "sig": sig}


def verify_download(audio_id: str, exp: int, sig: str) -> None:
    expected = _sign("download", audio_id, str(exp))
    if not hmac.compare_digest(expected, sig):
        raise SignedURLError("INVALID_SIGNATURE", "invalid or tampered signature")
    if int(time.time()) > exp:
        raise SignedURLError("URL_EXPIRED", "download URL has expired")
