"""DID-signed envelopes for invoices and receipts."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from .jws import ResolveKey, sign_compact, verify_compact
from .keys import verification_method_id

VERSION = "agent-pay/0.1"


@dataclass(frozen=True)
class InvoiceEnvelope:
    v: str
    invoice_hash: str
    did: str
    price_msat: str
    resource: str
    expires_at: str
    nonce: str


@dataclass(frozen=True)
class ReceiptEnvelope:
    v: str
    invoice_hash: str
    preimage_hash: str
    resource: str
    paid_at: str
    did: str


def _hex(data: bytes) -> str:
    return data.hex()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _invoice_hash_hex(bolt11: str) -> str:
    return hashlib.sha256(bolt11.encode("utf-8")).hexdigest()


async def sign_invoice_envelope(
    *,
    bolt11: str,
    did: str,
    private_key: bytes,
    price_msat: int,
    resource: str,
    expires_at: str,
    nonce: bytes,
) -> str:
    payload = {
        "v": VERSION,
        "invoice_hash": _invoice_hash_hex(bolt11),
        "did": did,
        "price_msat": str(price_msat),
        "resource": resource,
        "expires_at": expires_at,
        "nonce": _b64(nonce),
    }
    return await sign_compact(payload, private_key, verification_method_id(did))


async def verify_invoice_envelope(
    token: str,
    *,
    bolt11: str,
    resolver: ResolveKey,
) -> InvoiceEnvelope:
    payload, _kid = await verify_compact(token, resolver)
    if payload.get("v") != VERSION:
        raise ValueError(f"unsupported envelope version: {payload.get('v')}")
    expected = _invoice_hash_hex(bolt11)
    if payload.get("invoice_hash") != expected:
        raise ValueError(
            f"invoice_hash mismatch: envelope={payload.get('invoice_hash')} bolt11={expected}"
        )
    return InvoiceEnvelope(
        v=payload["v"],
        invoice_hash=payload["invoice_hash"],
        did=payload["did"],
        price_msat=payload["price_msat"],
        resource=payload["resource"],
        expires_at=payload["expires_at"],
        nonce=payload["nonce"],
    )


async def sign_receipt(
    *,
    bolt11: str,
    did: str,
    private_key: bytes,
    preimage: bytes,
    resource: str,
    paid_at: str,
) -> str:
    payload = {
        "v": VERSION,
        "invoice_hash": _invoice_hash_hex(bolt11),
        "preimage_hash": _hex(hashlib.sha256(preimage).digest()),
        "resource": resource,
        "paid_at": paid_at,
        "did": did,
    }
    return await sign_compact(payload, private_key, verification_method_id(did))


async def verify_receipt(
    token: str,
    *,
    bolt11: str,
    resolver: ResolveKey,
) -> ReceiptEnvelope:
    payload, _kid = await verify_compact(token, resolver)
    if payload.get("v") != VERSION:
        raise ValueError(f"unsupported receipt version: {payload.get('v')}")
    if payload.get("invoice_hash") != _invoice_hash_hex(bolt11):
        raise ValueError("receipt invoice_hash mismatch")
    return ReceiptEnvelope(
        v=payload["v"],
        invoice_hash=payload["invoice_hash"],
        preimage_hash=payload["preimage_hash"],
        resource=payload["resource"],
        paid_at=payload["paid_at"],
        did=payload["did"],
    )
