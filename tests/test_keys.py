import pytest

from agent_pay.keys import (
    did_key_from_public_key,
    generate_key_pair,
    public_key_from_did_key,
    verification_method_id,
)


def test_generate_key_pair_returns_32_byte_secret_and_public() -> None:
    kp = generate_key_pair()
    assert len(kp.private_key) == 32
    assert len(kp.public_key) == 32


def test_did_key_roundtrips_ed25519_public_key() -> None:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    assert did.startswith("did:key:z")
    back = public_key_from_did_key(did)
    assert back == kp.public_key


def test_public_key_from_did_key_rejects_non_did_key() -> None:
    with pytest.raises(ValueError):
        public_key_from_did_key("did:web:example.com")


def test_verification_method_id_for_did_key_uses_multibase_as_fragment() -> None:
    did = "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"
    assert (
        verification_method_id(did)
        == f"{did}#z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"
    )
