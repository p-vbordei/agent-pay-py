"""Compact JWS over Ed25519 with JCS-canonical payload."""

from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .jcs import canonical_json
from .keys import ed25519_sign, ed25519_verify

ResolveKey = Callable[[str], Awaitable[bytes]]

_HEADER = {"alg": "EdDSA", "typ": "JWS"}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


async def sign_compact(payload: Any, private_key: bytes, kid: str) -> str:
    header_bytes = canonical_json({**_HEADER, "kid": kid})
    payload_bytes = canonical_json(payload)
    header_b64 = _b64url(header_bytes)
    payload_b64 = _b64url(payload_bytes)
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = ed25519_sign(private_key, signing_input)
    return f"{header_b64}.{payload_b64}.{_b64url(sig)}"


async def verify_compact(token: str, resolve_key: ResolveKey) -> tuple[Any, str]:
    """Return (payload, kid). Raises ValueError on any failure."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("compact JWS must have 3 parts")
    header_b64, payload_b64, sig_b64 = parts
    header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    alg = header.get("alg")
    if alg != "EdDSA":
        raise ValueError(f"unsupported JWS alg: {alg}")
    kid = header.get("kid")
    if not kid:
        raise ValueError("JWS header missing kid")
    public_key = await resolve_key(kid)
    signing_input = f"{header_b64}.{payload_b64}".encode()
    if not ed25519_verify(public_key, signing_input, _b64url_decode(sig_b64)):
        raise ValueError("JWS signature verification failed")
    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    return payload, kid
