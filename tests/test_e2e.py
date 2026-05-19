from agent_pay.client import fetch_with_l402
from agent_pay.keys import did_key_from_public_key, generate_key_pair
from agent_pay.memory_node import MemoryLedger, MemoryNode
from agent_pay.server import Paywall, PaywallOptions, PaywallResponse

from ._harness import make_fetch

SECRET = b"thirty-two-byte-test-secret-pad!"


async def test_e2e_roundtrip() -> None:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    server_node = MemoryNode(ledger=ledger, name="server")
    client_node = MemoryNode(ledger=ledger, name="client")

    paywall = Paywall(
        PaywallOptions(
            server_did=did,
            server_private_key=kp.private_key,
            price_msat=1234,
            resource="/report",
            lightning=server_node,
            token_secret=SECRET,
        )
    )

    async def handler(_p: str, _h: dict[str, str]) -> PaywallResponse:
        return PaywallResponse(status=200, json={"ok": True, "body": "paid content"})

    fetch = make_fetch(paywall, handler)
    res = await fetch_with_l402(
        "http://x/report",
        wallet=client_node,
        max_price_msat=5000,
        expected_did=did,
        fetch=fetch,
    )
    assert res.status == 200
    assert res.json_body == {"ok": True, "body": "paid content"}
