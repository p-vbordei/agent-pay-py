"""In-memory mock Lightning node (mirrors the TS memory-node)."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field

import bolt11 as _bolt11
from bolt11 import Bolt11, MilliSatoshi
from bolt11.models.tags import Tag, TagChar, Tags

from .lightning import (
    Invoice,
    InvoiceCreateRequest,
    InvoiceLookup,
    PaymentResult,
)

_SIGNING_KEY_HEX = "e126f68f7eafcc8b74f54d269fe206be715000f94dac067d1c04a8ca3b2db734"


@dataclass
class _Entry:
    amount_msat: int
    payment_hash: str
    preimage: bytes
    bolt11: str
    settled: bool
    payee: str


@dataclass
class MemoryLedger:
    invoices: dict[str, _Entry] = field(default_factory=dict)


class MemoryNode:
    def __init__(self, *, ledger: MemoryLedger, name: str) -> None:
        self._ledger = ledger
        self._name = name

    async def create_invoice(self, req: InvoiceCreateRequest) -> Invoice:
        preimage = os.urandom(32)
        payment_hash = hashlib.sha256(preimage).hexdigest()
        # The bolt11 pypi package requires payment_secret per BOLT11 modern spec.
        payment_secret = os.urandom(32).hex()
        inv = Bolt11(
            currency="bcrt",
            date=int(time.time()),
            amount_msat=MilliSatoshi(req.amount_msat),
            tags=Tags(
                [
                    Tag(TagChar.payment_hash, payment_hash),
                    Tag(TagChar.description, req.memo or ""),
                    Tag(TagChar.expire_time, req.expiry_seconds or 300),
                    Tag(TagChar.payment_secret, payment_secret),
                ]
            ),
        )
        payment_request = _bolt11.encode(inv, _SIGNING_KEY_HEX)
        self._ledger.invoices[payment_hash] = _Entry(
            amount_msat=req.amount_msat,
            payment_hash=payment_hash,
            preimage=preimage,
            bolt11=payment_request,
            settled=False,
            payee=self._name,
        )
        return Invoice(bolt11=payment_request, payment_hash=payment_hash)

    async def lookup_invoice(self, payment_hash: str) -> InvoiceLookup:
        entry = self._ledger.invoices.get(payment_hash)
        if entry is None:
            raise ValueError(f"unknown payment_hash: {payment_hash}")
        return InvoiceLookup(
            settled=entry.settled,
            amount_msat=entry.amount_msat,
            preimage=entry.preimage if entry.settled else None,
        )

    async def pay_invoice(self, bolt11: str) -> PaymentResult:
        for entry in self._ledger.invoices.values():
            if entry.bolt11 == bolt11:
                if entry.settled:
                    raise ValueError("invoice already settled")
                entry.settled = True
                return PaymentResult(preimage=entry.preimage, fee_msat=0)
        raise ValueError(f"unknown bolt11: {bolt11[:32]}...")
