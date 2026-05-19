"""agent-pay (Python) quickstart — full L402 round-trip, no real Lightning node.

A `Paywall` issues a 402 with a DID-signed BOLT11 invoice. A client wallet
(another `MemoryNode` sharing the same in-memory ledger) pays the invoice,
retries with `Authorization: L402 <token>:<preimage>`, and the paywall hands
back a signed `X-Payment-Receipt` plus the gated payload.

Run with: `uv run python examples/quickstart.py`
"""

from __future__ import annotations

import asyncio

from agent_pay import (
    MemoryLedger,
    MemoryNode,
    did_key_from_public_key,
    generate_key_pair,
)
from agent_pay.client import FetchResponse, fetch_with_l402
from agent_pay.server import Paywall, PaywallOptions, PaywallResponse

SECRET = b"thirty-two-byte-test-secret-pad!"


async def main() -> None:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    server_node = MemoryNode(ledger=ledger, name="server")
    client_node = MemoryNode(ledger=ledger, name="client")

    paywall = Paywall(
        PaywallOptions(
            server_did=did,
            server_private_key=kp.private_key,
            price_msat=1000,
            resource="/report",
            lightning=server_node,
            token_secret=SECRET,
        )
    )

    async def handler(_path: str, _headers: dict[str, str]) -> PaywallResponse:
        return PaywallResponse(status=200, json={"insight": "agents charging agents works."})

    async def fetch(url: str, headers: dict[str, str] | None) -> FetchResponse:
        path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        resp = await paywall.process_request(headers or {}, handler, path=path)
        return FetchResponse(
            status=resp.status, headers=dict(resp.headers), json_body=resp.json
        )

    print(f"server DID: {did}")
    res = await fetch_with_l402(
        "http://x/report",
        wallet=client_node,
        max_price_msat=5000,
        expected_did=did,
        fetch=fetch,
    )
    receipt = res.header("x-payment-receipt") or ""
    print(f"status:  {res.status}")
    print(f"payload: {res.json_body}")
    print(f"receipt: {receipt[:64]}{'...' if len(receipt) > 64 else ''}")


if __name__ == "__main__":
    asyncio.run(main())
