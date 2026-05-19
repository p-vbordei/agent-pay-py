"""BOLT11 parsing wrapper (uses the `bolt11` PyPI package)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import bolt11 as _bolt11


@dataclass(frozen=True)
class ParsedInvoice:
    payment_hash: str
    amount_msat: int
    expiry_at: datetime | None
    raw: Any


def parse_invoice(input_str: str) -> ParsedInvoice:
    decoded = _bolt11.decode(input_str)
    payment_hash = decoded.payment_hash
    if not payment_hash:
        raise ValueError("bolt11: missing payment_hash")
    amount_msat = int(decoded.amount_msat) if decoded.amount_msat else 0
    expiry_at: datetime | None = None
    if decoded.expiry is not None and decoded.date is not None:
        expiry_at = datetime.fromtimestamp(decoded.date + decoded.expiry, tz=UTC)
    return ParsedInvoice(
        payment_hash=payment_hash,
        amount_msat=amount_msat,
        expiry_at=expiry_at,
        raw=decoded,
    )
