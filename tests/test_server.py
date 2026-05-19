import base64
import json

from agent_pay.client import fetch_with_l402
from agent_pay.keys import did_key_from_public_key, generate_key_pair
from agent_pay.memory_node import MemoryLedger, MemoryNode
from agent_pay.server import Paywall, PaywallOptions

from ._harness import echo_handler, make_fetch, make_raw_fetch

SECRET = b"thirty-two-byte-test-secret-pad!"


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _setup() -> tuple[Paywall, MemoryLedger, str]:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    lightning = MemoryNode(ledger=ledger, name="server")
    paywall = Paywall(
        PaywallOptions(
            server_did=did,
            server_private_key=kp.private_key,
            price_msat=1000,
            resource="/report",
            lightning=lightning,
            token_secret=SECRET,
        )
    )
    return paywall, ledger, did


async def test_first_request_returns_402_with_x_did_invoice() -> None:
    paywall, _ledger, _did = _setup()
    raw = make_raw_fetch(paywall, echo_handler)
    res = await raw("http://x/report", None)
    assert res.status == 402
    assert res.headers["www-authenticate"].startswith("L402 ")
    assert 'macaroon="' in res.headers["www-authenticate"]
    assert 'invoice="' in res.headers["www-authenticate"]
    assert res.headers["x-did-invoice"]


async def test_each_402_carries_a_fresh_nonce() -> None:
    paywall, _ledger, _did = _setup()
    raw = make_raw_fetch(paywall, echo_handler)

    async def nonce_from() -> str:
        res = await raw("http://x/report", None)
        jws = res.headers["x-did-invoice"]
        payload_b64 = jws.split(".")[1]
        payload = json.loads(_b64url_decode(payload_b64))
        return payload["nonce"]

    n1 = await nonce_from()
    n2 = await nonce_from()
    assert n1 != n2


async def test_replayed_preimage_returns_401() -> None:
    paywall, ledger, _did = _setup()
    wallet = MemoryNode(ledger=ledger, name="wallet")

    captured: dict[str, str] = {}

    async def recorder(url: str, headers: dict[str, str] | None) -> object:
        if headers and headers.get("authorization", "").startswith("L402 "):
            captured["auth"] = headers["authorization"]
        return await make_fetch(paywall, echo_handler)(url, headers)

    ok = await fetch_with_l402(
        "http://x/report",
        wallet=wallet,
        max_price_msat=5000,
        fetch=recorder,  # type: ignore[arg-type]
    )
    assert ok.status == 200
    assert "auth" in captured

    raw = make_raw_fetch(paywall, echo_handler)
    replay = await raw("http://x/report", {"authorization": captured["auth"]})
    assert replay.status == 401
    assert "replay" in replay.json["error"]
