"""Short-lived HMAC-signed tokens for audio preview streaming."""
from __future__ import annotations

import hashlib
import hmac
import time

from app.config import get_settings

settings = get_settings()


class SignedURLError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sign(audio_id: str, start: int, exp: int) -> str:
    msg = f"{audio_id}:{start}:{exp}"
    return hmac.new(settings.SIGNED_URL_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def issue(audio_id: str, start: int) -> dict:
    exp = int(time.time()) + settings.SIGNED_URL_TTL_SECONDS
    return {"audio_id": audio_id, "start": start, "exp": exp, "sig": _sign(audio_id, start, exp)}


def verify(audio_id: str, start: int, exp: int, sig: str) -> None:
    expected = _sign(audio_id, start, exp)
    if not hmac.compare_digest(expected, sig):
        raise SignedURLError("INVALID_SIGNATURE", "invalid or tampered signature")
    if int(time.time()) > exp:
        raise SignedURLError("URL_EXPIRED", "stream URL has expired")
