from datetime import UTC, datetime, timedelta

import pytest

from agent_pay.client import FetchResponse, FetchWithL402Error, fetch_with_l402
from agent_pay.envelope import sign_invoice_envelope
from agent_pay.keys import did_key_from_public_key, generate_key_pair
from agent_pay.lightning import InvoiceCreateRequest
from agent_pay.memory_node import MemoryLedger, MemoryNode
from agent_pay.server import Paywall, PaywallOptions
from agent_pay.token import issue_token

from ._harness import echo_handler, make_fetch, ok_handler

SECRET = b"thirty-two-byte-test-secret-pad!"


def _common_setup(
    price_msat: int = 1000, ttl: int = 300
) -> tuple[Paywall, MemoryLedger, str, bytes]:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    server_node = MemoryNode(ledger=ledger, name="server")
    paywall = Paywall(
        PaywallOptions(
            server_did=did,
            server_private_key=kp.private_key,
            price_msat=price_msat,
            resource="/report",
            lightning=server_node,
            token_secret=SECRET,
            invoice_ttl_seconds=ttl,
        )
    )
    return paywall, ledger, did, kp.private_key


async def test_fetch_with_l402_pays_via_fake_node_retries_and_parses_200() -> None:
    paywall, ledger, _did, _ = _common_setup()
    client_node = MemoryNode(ledger=ledger, name="client")
    fetch = make_fetch(paywall, echo_handler)
    res = await fetch_with_l402(
        "http://x/report",
        wallet=client_node,
        max_price_msat=5000,
        fetch=fetch,
    )
    assert res.status == 200
    assert res.json_body == {"data": "hello"}
    assert res.header("x-payment-receipt")


async def test_overcharging_bolt11_amount_must_equal_envelope_price() -> None:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    node = MemoryNode(ledger=ledger, name="server")
    wallet = MemoryNode(ledger=ledger, name="client")

    # Custom challenge that lies: BOLT11 = 9999msat but envelope claims 1000.
    async def lying_fetch(_url: str, _headers: dict[str, str] | None) -> FetchResponse:
        inv = await node.create_invoice(InvoiceCreateRequest(amount_msat=9999))
        envelope = await sign_invoice_envelope(
            bolt11=inv.bolt11,
            did=did,
            private_key=kp.private_key,
            price_msat=1000,
            resource="/lying",
            expires_at="2030-01-01T00:00:00Z",
            nonce=bytes(16),
        )
        tok = await issue_token(
            payment_hash=inv.payment_hash,
            expires_at="2030-01-01T00:00:00Z",
            secret=SECRET,
        )
        return FetchResponse(
            status=402,
            headers={
                "www-authenticate": f'L402 macaroon="{tok}", invoice="{inv.bolt11}"',
                "x-did-invoice": envelope,
            },
        )

    with pytest.raises(FetchWithL402Error, match=r"(amount|mismatch)"):
        await fetch_with_l402(
            "http://x/lying",
            wallet=wallet,
            max_price_msat=50_000,
            fetch=lying_fetch,
        )


async def test_throws_when_receipt_jws_is_tampered() -> None:
    paywall, ledger, _did, _ = _common_setup()
    wallet = MemoryNode(ledger=ledger, name="client")
    inner = make_fetch(paywall, ok_handler)

    async def tamperer(url: str, headers: dict[str, str] | None) -> FetchResponse:
        res = await inner(url, headers)
        receipt = res.header("x-payment-receipt")
        if not receipt:
            return res
        parts = receipt.split(".")
        if len(parts) != 3:
            return res
        sig = parts[2]
        parts[2] = ("B" if sig[0] == "A" else "A") + sig[1:]
        new_headers = dict(res.headers)
        new_headers["x-payment-receipt"] = ".".join(parts)
        return FetchResponse(
            status=res.status,
            headers=new_headers,
            body=res.body,
            json_body=res.json_body,
        )

    with pytest.raises(FetchWithL402Error, match="receipt"):
        await fetch_with_l402(
            "http://x/tamper",
            wallet=wallet,
            max_price_msat=5000,
            fetch=tamperer,
        )


async def test_client_enforces_max_price_msat_cap() -> None:
    paywall, ledger, _did, _ = _common_setup(price_msat=10_000)
    wallet = MemoryNode(ledger=ledger, name="client")
    fetch = make_fetch(paywall, ok_handler)
    with pytest.raises(FetchWithL402Error, match=r"(cap|exceeds)"):
        await fetch_with_l402(
            "http://x/r",
            wallet=wallet,
            max_price_msat=5000,
            fetch=fetch,
        )


async def test_client_rejects_envelope_past_expires_at() -> None:
    paywall, ledger, _did, _ = _common_setup(ttl=1)
    wallet = MemoryNode(ledger=ledger, name="client")
    fetch = make_fetch(paywall, ok_handler)
    with pytest.raises(FetchWithL402Error, match="expired"):
        await fetch_with_l402(
            "http://x/r",
            wallet=wallet,
            max_price_msat=5000,
            fetch=fetch,
            now=lambda: datetime.now(tz=UTC) + timedelta(seconds=10),
        )
