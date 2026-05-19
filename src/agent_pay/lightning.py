"""Lightning node protocol types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InvoiceCreateRequest:
    amount_msat: int
    memo: str | None = None
    expiry_seconds: int | None = None


@dataclass(frozen=True)
class Invoice:
    bolt11: str
    payment_hash: str


@dataclass(frozen=True)
class InvoiceLookup:
    settled: bool
    amount_msat: int
    preimage: bytes | None = None


@dataclass(frozen=True)
class PaymentResult:
    preimage: bytes
    fee_msat: int


class LightningNode(Protocol):
    async def create_invoice(self, req: InvoiceCreateRequest) -> Invoice: ...
    async def lookup_invoice(self, payment_hash: str) -> InvoiceLookup: ...
    async def pay_invoice(self, bolt11: str) -> PaymentResult: ...
