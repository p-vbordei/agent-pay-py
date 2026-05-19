"""RFC 8785 JSON Canonicalization Scheme + SHA-256 hash."""

from __future__ import annotations

import hashlib
from typing import Any

import jcs as _jcs


def canonical_json(value: Any) -> bytes:
    """Return the RFC 8785 canonical JSON encoding of ``value``."""
    return _jcs.canonicalize(value)


def jcs_hash(value: Any) -> bytes:
    """SHA-256 of the canonical JSON encoding."""
    return hashlib.sha256(canonical_json(value)).digest()
