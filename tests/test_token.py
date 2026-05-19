import pytest

from agent_pay.token import issue_token, verify_token

SECRET = b"thirty-two-byte-test-secret-pad!"


async def test_issue_token_verify_token_roundtrips_payment_hash_and_expires_at() -> None:
    tok = await issue_token(
        payment_hash="a" * 64,
        expires_at="2030-01-01T00:00:00Z",
        secret=SECRET,
    )
    payload = await verify_token(tok, SECRET)
    assert payload.payment_hash == "a" * 64
    assert payload.expires_at == "2030-01-01T00:00:00Z"


async def test_verify_token_rejects_hmac_mismatch() -> None:
    tok = await issue_token(
        payment_hash="a" * 64,
        expires_at="2030-01-01T00:00:00Z",
        secret=SECRET,
    )
    other = b"different-thirty-two-byte-secret"
    with pytest.raises(ValueError, match="HMAC"):
        await verify_token(tok, other)


async def test_verify_token_rejects_malformed_token() -> None:
    with pytest.raises(ValueError):
        await verify_token("not.a.valid.token", SECRET)
