"""Ed25519 key pair generation and did:key encoding."""

from __future__ import annotations

from dataclasses import dataclass

import base58
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ED25519_PUB_MULTICODEC = bytes([0xED, 0x01])


@dataclass(frozen=True)
class KeyPair:
    public_key: bytes
    private_key: bytes


def generate_key_pair() -> KeyPair:
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    return KeyPair(
        public_key=pk.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
        private_key=sk.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )


def did_key_from_public_key(public_key: bytes) -> str:
    if len(public_key) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(public_key)}")
    encoded = base58.b58encode(ED25519_PUB_MULTICODEC + public_key).decode("ascii")
    return f"did:key:z{encoded}"


def public_key_from_did_key(did: str) -> bytes:
    if not did.startswith("did:key:z"):
        raise ValueError(f"not a did:key: {did}")
    multibase = did[len("did:key:") :]
    decoded = base58.b58decode(multibase[1:])  # strip 'z' multibase prefix
    if len(decoded) < 34:
        raise ValueError(
            f"did:key multibase too short: decoded {len(decoded)} bytes "
            "(need 2-byte multicodec + 32-byte Ed25519 key)"
        )
    if decoded[0] != 0xED or decoded[1] != 0x01:
        got = f"0x{decoded[0]:02x}{decoded[1]:02x}"
        raise ValueError(
            f"unsupported did:key multicodec (expected 0xed01, got {got})"
        )
    return bytes(decoded[2:34])


def verification_method_id(did: str) -> str:
    if did.startswith("did:key:"):
        fragment = did[len("did:key:") :]
        return f"{did}#{fragment}"
    if "#" not in did:
        raise ValueError(f"cannot derive fragment from {did}")
    return did


def ed25519_sign(private_key: bytes, message: bytes) -> bytes:
    sk = Ed25519PrivateKey.from_private_bytes(private_key)
    return sk.sign(message)


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    pk = Ed25519PublicKey.from_public_bytes(public_key)
    try:
        pk.verify(signature, message)
        return True
    except InvalidSignature:
        return False
