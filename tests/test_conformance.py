"""Conformance vectors C1-missing, C1-bad-sig, C2, C3, C4 against in-memory node."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_pay.client import FetchResponse, FetchWithL402Error, fetch_with_l402
from agent_pay.envelope import sign_invoice_envelope
from agent_pay.keys import did_key_from_public_key, generate_key_pair
from agent_pay.lightning import InvoiceCreateRequest
from agent_pay.memory_node import MemoryLedger, MemoryNode
from agent_pay.server import Paywall, PaywallOptions
from agent_pay.token import issue_token

from ._harness import make_fetch, make_raw_fetch, ok_handler

VECTORS = Path(__file__).resolve().parent.parent / "vectors"
SECRET = b"thirty-two-byte-test-secret-pad!"


def _base_setup(price_msat: int = 1000) -> tuple[Paywall, MemoryLedger, MemoryNode, str]:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    server_node = MemoryNode(ledger=ledger, name="server")
    wallet = MemoryNode(ledger=ledger, name="wallet")
    paywall = Paywall(
        PaywallOptions(
            server_did=did,
            server_private_key=kp.private_key,
            price_msat=price_msat,
            resource="/r",
            lightning=server_node,
            token_secret=SECRET,
        )
    )
    return paywall, ledger, wallet, did


async def _run(vector: dict[str, object]) -> None:
    scenario = vector["scenario"]
    if scenario == "C1-missing-x-did-invoice":
        paywall, _ledger, wallet, _did = _base_setup()
        inner = make_fetch(paywall, ok_handler)

        async def strip(url: str, headers: dict[str, str] | None) -> FetchResponse:
            res = await inner(url, headers)
            new_headers = {k: v for k, v in res.headers.items() if k.lower() != "x-did-invoice"}
            return FetchResponse(
                status=res.status, headers=new_headers, body=res.body, json_body=res.json_body
            )

        try:
            await fetch_with_l402(
                "http://x/r", wallet=wallet, max_price_msat=5000, fetch=strip
            )
        except FetchWithL402Error as e:
            if e.reason == "missing-x-did-invoice":
                return
            raise
        raise AssertionError("expected missing-x-did-invoice")

    if scenario == "C1-invalid-jws":
        paywall, _ledger, wallet, _did = _base_setup()
        inner = make_fetch(paywall, ok_handler)

        async def tamper(url: str, headers: dict[str, str] | None) -> FetchResponse:
            res = await inner(url, headers)
            jws = res.header("x-did-invoice")
            if not jws:
                return res
            parts = jws.split(".")
            if len(parts) == 3:
                sig = parts[2]
                parts[2] = ("B" if sig[0] == "A" else "A") + sig[1:]
            new_headers = dict(res.headers)
            new_headers["x-did-invoice"] = ".".join(parts)
            return FetchResponse(
                status=res.status, headers=new_headers, body=res.body, json_body=res.json_body
            )

        try:
            await fetch_with_l402(
                "http://x/r", wallet=wallet, max_price_msat=5000, fetch=tamper
            )
        except FetchWithL402Error as e:
            if e.reason == "jws-invalid":
                return
            raise
        raise AssertionError("expected jws-invalid")

    if scenario == "C2-roundtrip":
        paywall, _ledger, wallet, did = _base_setup()
        fetch = make_fetch(paywall, ok_handler)
        res = await fetch_with_l402(
            "http://x/r",
            wallet=wallet,
            max_price_msat=5000,
            expected_did=did,
            fetch=fetch,
        )
        assert res.status == 200, f"expected 200, got {res.status}"
        assert res.header("x-payment-receipt"), "missing x-payment-receipt"
        return

    if scenario == "C3-replayed-preimage":
        paywall, _ledger, wallet, _did = _base_setup()
        captured: dict[str, str] = {}
        inner = make_fetch(paywall, ok_handler)

        async def recorder(url: str, headers: dict[str, str] | None) -> FetchResponse:
            if headers and headers.get("authorization", "").startswith("L402 "):
                captured["auth"] = headers["authorization"]
            return await inner(url, headers)

        ok = await fetch_with_l402(
            "http://x/r", wallet=wallet, max_price_msat=5000, fetch=recorder
        )
        assert ok.status == 200, "first request should succeed"
        assert "auth" in captured
        raw = make_raw_fetch(paywall, ok_handler)
        replay = await raw("http://x/r", {"authorization": captured["auth"]})
        assert replay.status == 401, f"expected 401 on replay, got {replay.status}"
        return

    if scenario == "C4-bolt11-hash-mismatch":
        kp = generate_key_pair()
        did = did_key_from_public_key(kp.public_key)
        ledger = MemoryLedger()
        node = MemoryNode(ledger=ledger, name="liar")
        wallet = MemoryNode(ledger=ledger, name="wallet")

        async def liar(_url: str, _headers: dict[str, str] | None) -> FetchResponse:
            real = await node.create_invoice(InvoiceCreateRequest(amount_msat=1000))
            fake = await node.create_invoice(InvoiceCreateRequest(amount_msat=1000))
            env = await sign_invoice_envelope(
                bolt11=fake.bolt11,
                did=did,
                private_key=kp.private_key,
                price_msat=1000,
                resource="/r",
                expires_at="2030-01-01T00:00:00Z",
                nonce=bytes(16),
            )
            tok = await issue_token(
                payment_hash=real.payment_hash,
                expires_at="2030-01-01T00:00:00Z",
                secret=SECRET,
            )
            return FetchResponse(
                status=402,
                headers={
                    "www-authenticate": f'L402 macaroon="{tok}", invoice="{real.bolt11}"',
                    "x-did-invoice": env,
                },
            )

        try:
            await fetch_with_l402(
                "http://x/r", wallet=wallet, max_price_msat=5000, fetch=liar
            )
        except FetchWithL402Error as e:
            if e.reason == "jws-invalid":
                return
            raise
        raise AssertionError("expected jws-invalid")

    raise AssertionError(f"unknown scenario: {scenario}")


@pytest.mark.parametrize(
    "vector",
    [json.loads(p.read_text()) for p in sorted(VECTORS.glob("*.json"))],
    ids=lambda v: v["id"],
)
async def test_vector(vector: dict[str, object]) -> None:
    await _run(vector)
