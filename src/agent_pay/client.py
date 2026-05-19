"""L402-aware HTTP client. Mirrors fetchWithL402 from the TS reference."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .bolt11 import parse_invoice
from .envelope import verify_invoice_envelope, verify_receipt
from .keys import public_key_from_did_key
from .lightning import LightningNode

CHALLENGE_RE = re.compile(r'macaroon="([^"]+)",\s*invoice="([^"]+)"')


class FetchWithL402Error(Exception):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass
class FetchResponse:
    """Minimal response shape understood by `fetch_with_l402`."""

    status: int
    headers: dict[str, str]
    body: bytes | None = None
    json_body: object = None

    def header(self, name: str) -> str | None:
        # case-insensitive lookup
        lower = name.lower()
        for k, v in self.headers.items():
            if k.lower() == lower:
                return v
        return None


FetchFn = Callable[[str, dict[str, str] | None], Awaitable[FetchResponse]]


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _parse_iso_ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


async def fetch_with_l402(
    url: str,
    *,
    wallet: LightningNode,
    max_price_msat: int,
    fetch: FetchFn,
    expected_did: str | None = None,
    verify_receipt_flag: bool = True,
    now: Callable[[], datetime] | None = None,
    method: str = "GET",
    request_headers: dict[str, str] | None = None,
) -> FetchResponse:
    now_fn = now or _now_utc
    request_headers = dict(request_headers or {})

    first = await fetch(url, request_headers)
    if first.status != 402:
        return first

    www_auth = first.header("www-authenticate") or ""
    challenge_match = CHALLENGE_RE.search(www_auth)
    if not challenge_match:
        raise FetchWithL402Error("no L402 challenge", "missing-challenge")
    token, bolt11 = challenge_match.group(1), challenge_match.group(2)

    envelope_jws = first.header("x-did-invoice")
    if not envelope_jws:
        raise FetchWithL402Error("missing X-Did-Invoice", "missing-x-did-invoice")

    resolver = _make_did_key_resolver(expected_did)
    try:
        env = await verify_invoice_envelope(
            envelope_jws, bolt11=bolt11, resolver=resolver
        )
    except Exception as e:
        raise FetchWithL402Error(
            f"X-Did-Invoice verification failed: {e}", "jws-invalid"
        ) from e

    if int(env.price_msat) > max_price_msat:
        raise FetchWithL402Error(
            f"price {env.price_msat} exceeds cap {max_price_msat}", "price-cap"
        )
    if _parse_iso_ms(env.expires_at) <= int(now_fn().timestamp() * 1000):
        raise FetchWithL402Error(
            f"invoice expired ({env.expires_at})", "expired"
        )

    parsed = parse_invoice(bolt11)
    if parsed.amount_msat != int(env.price_msat):
        raise FetchWithL402Error(
            f"BOLT11 amount {parsed.amount_msat} mismatches envelope price {env.price_msat}",
            "amount-mismatch",
        )

    pay = await wallet.pay_invoice(bolt11)
    preimage_hex = pay.preimage.hex()

    second_headers = {**request_headers, "authorization": f"L402 {token}:{preimage_hex}"}
    second = await fetch(url, second_headers)
    if second.status != 200:
        return second

    if verify_receipt_flag:
        receipt = second.header("x-payment-receipt")
        if receipt:
            try:
                await verify_receipt(receipt, bolt11=bolt11, resolver=resolver)
            except Exception as e:
                raise FetchWithL402Error(
                    f"receipt verification failed: {e}", "receipt-invalid"
                ) from e
    return second


def _make_did_key_resolver(
    pinned: str | None = None,
) -> Callable[[str], Awaitable[bytes]]:
    async def resolver(kid: str) -> bytes:
        did = kid.split("#")[0] if "#" in kid else kid
        if pinned and did != pinned:
            raise ValueError(f"unexpected DID {did}")
        return public_key_from_did_key(did)

    return resolver
