"""agent-pay - L402 + DID-signed invoices for agent-to-agent Lightning payments."""

from .bolt11 import ParsedInvoice, parse_invoice
from .envelope import (
    InvoiceEnvelope,
    ReceiptEnvelope,
    sign_invoice_envelope,
    sign_receipt,
    verify_invoice_envelope,
    verify_receipt,
)
from .jcs import canonical_json, jcs_hash
from .jws import ResolveKey, sign_compact, verify_compact
from .keys import (
    KeyPair,
    did_key_from_public_key,
    generate_key_pair,
    public_key_from_did_key,
    verification_method_id,
)
from .lightning import (
    Invoice,
    InvoiceCreateRequest,
    InvoiceLookup,
    LightningNode,
    PaymentResult,
)
from .memory_node import MemoryLedger, MemoryNode
from .replay import ReplayCache
from .token import TokenPayload, issue_token, verify_token

VERSION = "agent-pay/0.1"

__all__ = [
    "VERSION",
    "Invoice",
    "InvoiceCreateRequest",
    "InvoiceEnvelope",
    "InvoiceLookup",
    "KeyPair",
    "LightningNode",
    "MemoryLedger",
    "MemoryNode",
    "ParsedInvoice",
    "PaymentResult",
    "ReceiptEnvelope",
    "ReplayCache",
    "ResolveKey",
    "TokenPayload",
    "canonical_json",
    "did_key_from_public_key",
    "generate_key_pair",
    "issue_token",
    "jcs_hash",
    "parse_invoice",
    "public_key_from_did_key",
    "sign_compact",
    "sign_invoice_envelope",
    "sign_receipt",
    "verification_method_id",
    "verify_compact",
    "verify_invoice_envelope",
    "verify_receipt",
    "verify_token",
]
