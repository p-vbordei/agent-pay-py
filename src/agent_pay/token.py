"""HMAC-signed macaroon-style L402 tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from .jcs import canonical_json

VERSION = "agent-pay/0.1"


@dataclass(frozen=True)
class TokenPayload:
    v: str
    payment_hash: str
    expires_at: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


async def issue_token(
    *,
    payment_hash: str,
    expires_at: str,
    secret: bytes,
) -> str:
    payload = {
        "v": VERSION,
        "payment_hash": payment_hash,
        "expires_at": expires_at,
    }
    payload_bytes = canonical_json(payload)
    sig = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
    return f"{_b64url(payload_bytes)}.{_b64url(sig)}"


async def verify_token(token: str, secret: bytes) -> TokenPayload:
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("token must have 2 parts")
    payload_b64, sig_b64 = parts
    payload_bytes = _b64url_decode(payload_b64)
    expected = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
    got = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected, got):
        raise ValueError("token HMAC verification failed")
    payload = json.loads(payload_bytes.decode("utf-8"))
    if payload.get("v") != VERSION:
        raise ValueError(f"unsupported token version: {payload.get('v')}")
    return TokenPayload(
        v=payload["v"],
        payment_hash=payload["payment_hash"],
        expires_at=payload["expires_at"],
    )
