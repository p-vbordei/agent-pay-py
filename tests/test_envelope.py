import pytest

from agent_pay.envelope import (
    sign_invoice_envelope,
    sign_receipt,
    verify_invoice_envelope,
    verify_receipt,
)
from agent_pay.keys import (
    did_key_from_public_key,
    generate_key_pair,
    public_key_from_did_key,
)

FAKE_BOLT11 = "lnbc10n1pdummy"


async def _setup() -> tuple[bytes, str, str, object]:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)

    async def resolver(kid: str) -> bytes:
        if not kid.startswith(did):
            raise ValueError(f"unknown kid {kid}")
        return public_key_from_did_key(did)

    return kp.private_key, kp.public_key, did, resolver


async def test_sign_verify_invoice_envelope_roundtrip() -> None:
    sk, _pk, did, resolver = await _setup()
    token = await sign_invoice_envelope(
        bolt11=FAKE_BOLT11,
        did=did,
        private_key=sk,
        price_msat=1000,
        resource="/report",
        expires_at="2030-01-01T00:00:00Z",
        nonce=bytes(16),
    )
    env = await verify_invoice_envelope(token, bolt11=FAKE_BOLT11, resolver=resolver)
    assert env.did == did
    assert env.price_msat == "1000"
    assert env.resource == "/report"


async def test_verify_invoice_envelope_rejects_mismatched_bolt11() -> None:
    sk, _pk, did, resolver = await _setup()
    token = await sign_invoice_envelope(
        bolt11=FAKE_BOLT11,
        did=did,
        private_key=sk,
        price_msat=1000,
        resource="/report",
        expires_at="2030-01-01T00:00:00Z",
        nonce=bytes(16),
    )
    with pytest.raises(ValueError, match="invoice_hash"):
        await verify_invoice_envelope(
            token, bolt11="lnbc1pdifferent", resolver=resolver
        )


async def test_sign_verify_receipt_roundtrip() -> None:
    sk, _pk, did, resolver = await _setup()
    token = await sign_receipt(
        bolt11=FAKE_BOLT11,
        did=did,
        private_key=sk,
        preimage=bytes(32),
        resource="/report",
        paid_at="2030-01-01T00:00:00Z",
    )
    env = await verify_receipt(token, bolt11=FAKE_BOLT11, resolver=resolver)
    assert env.did == did
    assert env.resource == "/report"
