"""Paywall server: emits 402 challenges, validates L402 Authorization."""

from __future__ import annotations

import hmac
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .envelope import sign_invoice_envelope, sign_receipt
from .lightning import LightningNode
from .replay import ReplayCache
from .token import issue_token, verify_token

AUTH_RE = re.compile(r"^L402\s+([^:\s]+):([0-9a-fA-F]+)$")


@dataclass
class PaywallResponse:
    """A pure-data response used by the in-process Paywall — adapters convert to
    framework-specific Response objects."""

    status: int
    body: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)
    json: Any = None


# Inner handler: receives the raw request path/headers and returns a response.
InnerHandler = Callable[[str, dict[str, str]], Awaitable[PaywallResponse]]


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime) -> str:
    # Mirror JS Date.toISOString(): millisecond precision, Z suffix.
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _parse_iso_ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


@dataclass
class PaywallOptions:
    server_did: str
    server_private_key: bytes
    price_msat: int
    resource: str
    lightning: LightningNode
    token_secret: bytes
    invoice_ttl_seconds: int = 300
    now: Callable[[], datetime] = field(default=_now_utc)
    replay: ReplayCache | None = None


class Paywall:
    """Composable middleware. Use `process_request` to delegate handling, and
    pass `inner` (your business logic) which is invoked iff the request is paid.
    """

    def __init__(self, opts: PaywallOptions) -> None:
        self._opts = opts
        self._replay = opts.replay or ReplayCache()
        self._issued: dict[str, str] = {}

    async def process_request(
        self,
        headers: dict[str, str],
        inner: InnerHandler | None = None,
        *,
        path: str | None = None,
    ) -> PaywallResponse:
        auth = headers.get("authorization") or headers.get("Authorization")
        if not auth:
            return await self._challenge()
        m = AUTH_RE.match(auth)
        if not m:
            return await self._challenge()
        token, preimage_hex = m.group(1), m.group(2)
        try:
            payload = await verify_token(token, self._opts.token_secret)
        except Exception:
            return await self._challenge()
        if self._replay.is_used(payload.payment_hash):
            return PaywallResponse(
                status=401, json={"error": "preimage replayed"}
            )
        lookup = await self._opts.lightning.lookup_invoice(payload.payment_hash)
        if not lookup.settled or not lookup.preimage:
            return PaywallResponse(status=401, json={"error": "invoice not settled"})
        presented = bytes.fromhex(preimage_hex)
        if not hmac.compare_digest(presented, lookup.preimage):
            return PaywallResponse(
                status=401, json={"error": "preimage does not match settled invoice"}
            )
        self._replay.mark_used(payload.payment_hash, _parse_iso_ms(payload.expires_at))
        # Pass-through to inner.
        if inner is None:
            inner_resp = PaywallResponse(status=200)
        else:
            inner_resp = await inner(path or self._opts.resource, headers)
        bolt11 = self._issued.get(payload.payment_hash)
        if bolt11:
            receipt = await sign_receipt(
                bolt11=bolt11,
                did=self._opts.server_did,
                private_key=self._opts.server_private_key,
                preimage=presented,
                resource=self._opts.resource,
                paid_at=_iso(self._opts.now()),
            )
            inner_resp.headers["x-payment-receipt"] = receipt
        return inner_resp

    async def _challenge(self) -> PaywallResponse:
        ttl = self._opts.invoice_ttl_seconds
        from .lightning import InvoiceCreateRequest

        invoice = await self._opts.lightning.create_invoice(
            InvoiceCreateRequest(amount_msat=self._opts.price_msat, expiry_seconds=ttl)
        )
        self._issued[invoice.payment_hash] = invoice.bolt11
        now = self._opts.now()
        expires_at = _iso(
            datetime.fromtimestamp(now.timestamp() + ttl, tz=UTC)
        )
        nonce = os.urandom(16)
        envelope = await sign_invoice_envelope(
            bolt11=invoice.bolt11,
            did=self._opts.server_did,
            private_key=self._opts.server_private_key,
            price_msat=self._opts.price_msat,
            resource=self._opts.resource,
            expires_at=expires_at,
            nonce=nonce,
        )
        token = await issue_token(
            payment_hash=invoice.payment_hash,
            expires_at=expires_at,
            secret=self._opts.token_secret,
        )
        return PaywallResponse(
            status=402,
            headers={
                "www-authenticate": f'L402 macaroon="{token}", invoice="{invoice.bolt11}"',
                "x-did-invoice": envelope,
            },
        )
