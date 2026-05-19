import base64
import json

import pytest

from agent_pay.jws import sign_compact, verify_compact
from agent_pay.keys import (
    did_key_from_public_key,
    generate_key_pair,
    public_key_from_did_key,
    verification_method_id,
)


async def test_compact_jws_roundtrips_a_json_payload() -> None:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    kid = verification_method_id(did)
    payload = {"v": "agent-pay/0.1", "hello": "world"}
    token = await sign_compact(payload, kp.private_key, kid)
    assert len(token.split(".")) == 3

    async def resolver(k: str) -> bytes:
        assert k == kid
        return public_key_from_did_key(did)

    p, k = await verify_compact(token, resolver)
    assert p == payload
    assert k == kid


async def test_verify_compact_rejects_tampered_payload() -> None:
    kp = generate_key_pair()
    kid = verification_method_id(did_key_from_public_key(kp.public_key))
    token = await sign_compact({"a": 1}, kp.private_key, kid)
    h, p, s = token.split(".")
    bad = f"{h}.{p}AA.{s}"

    async def resolver(_kid: str) -> bytes:
        return kp.public_key

    with pytest.raises(ValueError, match="signature"):
        await verify_compact(bad, resolver)


async def test_verify_compact_rejects_unsupported_alg() -> None:
    def b64url(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

    header = b64url(json.dumps({"alg": "HS256", "kid": "x"}).encode())
    payload = b64url(json.dumps({"a": 1}).encode())
    sig = "AAAA"
    token = f"{header}.{payload}.{sig}"

    async def resolver(_kid: str) -> bytes:
        return b"\x00" * 32

    with pytest.raises(ValueError, match="alg"):
        await verify_compact(token, resolver)
